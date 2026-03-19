import numpy as np
import pydicom
# import os
from functools import lru_cache
from typing import Optional
import logging
import pathlib
import pandas as pd


# 로깅 설정
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 상수 정의
MIN_DOSERATE = 1.4  # (MU/s)    
MAX_SPEED = 20.0 * 100  # (cm/s)
MIN_SPEED = 0.1 * 100  # (cm/s)
TIME_RESOLUTION = 0.1/1000  # (s)
DOSERATE_TABLE_PATH = 'LS_doserate.csv'

class LineSegment:
    """개별 라인 세그먼트 정보"""
    __slots__ = ('position', 'weight', 'distance', 'dose_rate', 
                'raw_scan_time', 'rounded_scan_time', 'mu_per_dist', 
                'speed', 'energy')
    
    def __init__(self, position: Optional[np.ndarray] = None, 
                weight: float = 0.0, distance: float = 0.0) -> None:
        self.position = position  # 위치 좌표 (x, y)
        self.weight = weight      # 가중치 (MU)
        self.distance = distance  # 다음 세그먼트까지의 거리 (cm)
        
        # 계산된 값들
        self.dose_rate = 0.0      # 선량율 (MU/s)
        self.raw_scan_time = 0.0  # 실제 스캔 시간 (초)
        self.rounded_scan_time = 0.0  # 반올림된 스캔 시간 (초)
        self.mu_per_dist = 0.0    # 거리당 MU (MU/cm)
        self.speed = 0.0          # 속도 (cm/s)
        self.energy = 0.0         # 에너지

class Layer:
    """레이어 정보"""
    __slots__ = ('energy', 'cum_weight_now', 'cum_weight_next', 'positions', 
                'weights', 'mlc_positions', 'num_positions', 'tune_id', 'line_segments', 
                'total_mu', 'total_scan_time', 'layer_doserate')
    
    def __init__(self, energy: float = 0.0, cum_weight_now: float = 0.0, 
                cum_weight_next: float = 0.0, positions: Optional[np.ndarray] = None, 
                weights: Optional[np.ndarray] = None, mlc_positions: Optional[np.ndarray] = None, 
                num_positions: str = "", tune_id: str = "") -> None:
        self.energy = energy                # 에너지 (MeV)
        self.cum_weight_now = cum_weight_now    # 현재 누적 가중치
        self.cum_weight_next = cum_weight_next  # 다음 누적 가중치
        self.positions = positions          # 위치 배열 (n, 2)
        self.weights = weights              # 가중치 배열 (n, 1)
        self.mlc_positions = mlc_positions  # MLC positions (46, 2)
        self.num_positions = num_positions  # 포지션 수 정보
        self.tune_id = tune_id              # 튜닝 ID
        
        # 계산될 값들
        self.line_segments = []             # 라인 세그먼트 객체 리스트
        self.total_mu = 0.0                 # 총 MU
        self.total_scan_time = 0.0          # 총 스캔 시간
        self.layer_doserate = 0.0           # 레이어 선량율
        
        # 라인 세그먼트 생성
        self._create_line_segments()
        
    def _create_line_segments(self) -> None:
        """포지션과 가중치 정보로부터 라인 세그먼트 객체 생성"""
        if self.positions is None or self.weights is None:
            return
            
        num_segments = self.positions.shape[0]
        self.line_segments = [LineSegment() for _ in range(num_segments)]
        
        # 첫 번째 세그먼트 초기화
        self.line_segments[0].position = self.positions[0]
        self.line_segments[0].weight = self.weights[0] if len(self.weights) > 0 else 0.0
        self.line_segments[0].energy = self.energy
        
        # 나머지 세그먼트 초기화
        if num_segments > 1:
            # 벡터화된 거리 계산
            diff_vectors = np.diff(self.positions, axis=0)
            distances = np.sqrt(np.sum(diff_vectors**2, axis=1))
            
            for i in range(1, num_segments):
                self.line_segments[i].position = self.positions[i]
                self.line_segments[i].weight = self.weights[i] if i < len(self.weights) else 0.0
                self.line_segments[i].distance = distances[i-1]
                self.line_segments[i].energy = self.energy
            
            # 임시 변수 해제
            del diff_vectors
        
        # 총 MU 계산
        self.total_mu = np.round(self.cum_weight_next - self.cum_weight_now, 3)
        
    def calculate_scan_times(self, doserate_provider: float, 
                            min_doserate: float = MIN_DOSERATE, 
                            max_speed: float = MAX_SPEED, 
                            time_resolution: float = TIME_RESOLUTION) -> None:
        """모든 라인 세그먼트의 스캔 시간 계산"""
        num_segments = len(self.line_segments)
        if num_segments <= 1:
            return
            
        # 배열 초기화 (벡터 연산 준비)
        segments = self.line_segments[1:]
        num_valid_segments = len(segments)
        
        if num_valid_segments == 0:
            return
            
        # 벡터화된 계산을 위한 배열 준비
        distances = np.array([seg.distance for seg in segments])
        weights = np.array([seg.weight for seg in segments])
        
        # MU/cm 계산 (벡터화)
        mu_per_dist = np.zeros_like(weights)
        mask = distances > 0
        mu_per_dist[mask] = weights[mask] / distances[mask]
        
        # 임시 선량율 계산 (벡터화)
        dose_rates = max_speed * mu_per_dist
        
        # 레이어의 선량율 결정
        if len(dose_rates) > 0:
            min_dr = np.min(dose_rates)
            if min_dr < min_doserate:
                self.layer_doserate = min_doserate
            elif min_dr > doserate_provider:
                self.layer_doserate = doserate_provider
            else:
                self.layer_doserate = min_dr
        
        # 각 세그먼트에 계산 결과 할당
        for i, segment in enumerate(segments):
            segment.mu_per_dist = mu_per_dist[i]
            
            # 가중치가 매우 작은 경우 예외 처리
            if segment.weight < 1e-7:
                segment.raw_scan_time = segment.distance / max_speed
            else:
                segment.raw_scan_time = segment.weight / self.layer_doserate
                
            # 반올림된 스캔 시간
            segment.rounded_scan_time = time_resolution * round(segment.raw_scan_time / time_resolution)
            
            # 속도 계산
            if segment.mu_per_dist > 0:
                segment.speed = self.layer_doserate / segment.mu_per_dist
            else:
                segment.speed = max_speed
                
        
        # 메모리 해제
        del distances, weights, mu_per_dist, dose_rates
                
        # 총 스캔 시간 계산
        self.total_scan_time = sum(segment.rounded_scan_time for segment in self.line_segments)

class Port:
    """포트(빔) 정보를 저장하는 클래스"""
    __slots__ = ('layers', 'total_scan_time', 'aperture', 'mlc_y')
    
    def __init__(self) -> None:
        self.layers          = []   # 레이어 객체 리스트
        self.total_scan_time = 0.0  # 총 스캔 시간
        self.aperture        = []   # block shape
        self.mlc_y           = []   # mlc y positions

class LineScanningPosWtMQ:
    """Dicom RT 이온 계획 파일에서 위치와 가중치 정보를 추출하는 클래스"""
    def __init__(self, file_name: Optional[str] = None, debug_mode: bool = False) -> None:
        # 상수 정의
        self.MIN_DOSERATE = MIN_DOSERATE
        self.MAX_SPEED = MAX_SPEED
        self.MIN_SPEED = MIN_SPEED
        
        # 공개 속성 초기화
        self.ports = []           # 포트(빔) 정보 리스트
        self.result = []          # 결과값 (총 스캔 시간)
        self.debug_mode = debug_mode  # 디버깅 모드 여부
        
        # 숨겨진 속성 초기화
        self.RTion_name = file_name
        self._doserate_table = None
        self._energy_to_doserate = {}
        
        # 파일이 제공된 경우 바로 처리 시작
        if file_name is not None:
            self.process_file()
    
    @lru_cache(maxsize=1)  # 한 번만 로드하면 됨
    def _load_doserate_table(self) -> np.ndarray:
        """선량율 테이블을 로드하고 캐싱 (한 번만 로드)"""
        try:
            doserate_path = pathlib.Path(DOSERATE_TABLE_PATH)
            return np.loadtxt(doserate_path, delimiter=',', encoding='utf-8-sig')
        except FileNotFoundError:
            logger.error("선량율 테이블 파일을 찾을 수 없습니다.")
            return np.array([])
        except ValueError:
            logger.error("선량율 테이블 형식이 올바르지 않습니다.")
            return np.array([])
        except Exception as e:
            logger.error(f"선량율 테이블 로드 오류: {e}")
            return np.array([])
    
    @lru_cache(maxsize=64)  # 작은 파일에 적합한 크기 설정
    def get_doserate_for_energy(self, energy: float) -> float:
        """에너지에 대한 선량율 반환 (캐싱 활용)"""
        if energy in self._energy_to_doserate:
            return self._energy_to_doserate[energy]
            
        LS_doserate = self._load_doserate_table()
        if LS_doserate.size == 0:
            return 0
            
        # 해당 에너지에 대한 선량율 찾기
        mask = (LS_doserate[:, 0] >= energy + 0.0) & (LS_doserate[:, 0] < energy + 0.3)
        max_doserate_ind = np.where(mask)[0]
        
        if len(max_doserate_ind) > 0:
            max_doserate = LS_doserate[max_doserate_ind[0], 1]
            self._energy_to_doserate[energy] = max_doserate
            return max_doserate
        return 0
    
    def clear_caches(self) -> None:
        """메모리 확보를 위해 모든 캐시 정리"""
        self.get_doserate_for_energy.cache_clear()
        self._load_doserate_table.cache_clear()
        self._energy_to_doserate.clear()
    
    def process_file(self) -> None:
        """Dicom 파일을 처리하여 포트 및 레이어 정보 추출"""
        try:
            # Dicom 파일 읽기
            d_header = pydicom.dcmread(self.RTion_name)
            temp_port = list(d_header.IonBeamSequence)
                        
            # 각 포트(빔) 처리
            for i_port, port_name in enumerate(temp_port):
                port = Port()
                
                info_layer = port_name.IonControlPointSequence
                layers_info = list(info_layer)
                N_layers = len(layers_info) // 2
                
                # MLC position for each port
                if hasattr(port_name, 'IonBeamLimitingDeviceSequence'):
                    port.mlc_y = list(port_name.IonBeamLimitingDeviceSequence[0][0x300a, 0x00be])
                else:
                    port.mlc_y = None
                
                # Aperture information for each port
                # port.aperture.IBD = port_name.IonBlockSequence[0][0x300a, 0x00f7].value
                # port.aperture.thickness = port_name.IonBlockSequence[0][0x300a, 0x0100].value
                
                if int(port_name.NumberOfBlocks) > 0:
                     tmp_apt = 0.1*np.array(port_name.IonBlockSequence[0][0x300a, 0x0106].value, dtype=float)
                     port.aperture = np.reshape(tmp_apt, (len(tmp_apt)//2, 2))
                else:
                    port.aperture = None
                                
                # 각 레이어 처리
                for i_layer in range(N_layers):
                    jj = 2 * i_layer
                    
                    # 에너지 및 누적 가중치 정보
                    energy = layers_info[jj].NominalBeamEnergy
                    cum_weight_now = layers_info[jj].CumulativeMetersetWeight
                    cum_weight_next = layers_info[jj+1].CumulativeMetersetWeight
                    
                    # 라인 스캔 위치 맵
                    t1 = np.frombuffer(layers_info[jj][0x300b, 0x1094].value, dtype=np.float32)
                    positions = np.reshape(0.1*t1, (len(t1)//2, 2))
                    
                    # 라인 스캔 가중치
                    # t2 = np.frombuffer(layers_info[jj][0x300b, 0x1096].value, dtype=np.float32)
                    # weights = np.round(t2, 3)
                    weights = np.frombuffer(layers_info[jj][0x300b, 0x1096].value, dtype=np.float32)
                    
                    # mlc positions (cm)
                    if hasattr(port_name, 'IonBeamLimitingDeviceSequence'):
                        tmp_mlc_pos = 0.1*np.array(layers_info[jj][0x300a, 0x011a][0][0x300a, 0x011c].value, dtype=float)
                        mlc_pos = np.reshape(tmp_mlc_pos, (len(tmp_mlc_pos)//2, 2), order='F')
                    else:
                        mlc_pos = None
                    
                    # 기타 정보
                    num_positions = layers_info[jj][0x300b, 0x1092].value.decode('ascii').strip()
                    tune_id = layers_info[jj][0x300b, 0x1090].value.decode('ascii').strip()
                                        
                    # 레이어 객체 생성
                    layer = Layer(
                        energy=energy,
                        cum_weight_now=cum_weight_now,
                        cum_weight_next=cum_weight_next,
                        positions=positions,
                        weights=weights,
                        mlc_positions=mlc_pos,
                        num_positions=num_positions,
                        tune_id=tune_id
                    )
                    
                    # 스캔 시간 계산
                    layer.calculate_scan_times(
                        doserate_provider=self.get_doserate_for_energy(energy),
                        min_doserate=self.MIN_DOSERATE,
                        max_speed=self.MAX_SPEED
                    )
                    
                    # 레이어 정보 저장
                    port.layers.append(layer)
                    port.total_scan_time += layer.total_scan_time
                    
                    # 임시 변수 명시적 해제
                    del positions, weights, t1
                    
                # 포트 정보 저장                
                self.ports.append(port)
                self.result.append(port.total_scan_time)
                
            # 대용량 변수 명시적 해제
            del d_header
            del temp_port
                
        except pydicom.errors.InvalidDicomError:
            logger.error("유효하지 않은 DICOM 파일입니다.")
        except FileNotFoundError:
            logger.error(f"파일을 찾을 수 없습니다: {self.RTion_name}")
        except Exception as e:
            logger.exception(f"Dicom 처리 중 오류 발생: {e}")
                    
    def cleanup_resources(self) -> None:
        """메모리 사용 최적화를 위한 정리 작업 수행"""
        # 캐시 정리
        self.clear_caches()
        
        # 큰 객체 명시적 해제
        if hasattr(self, '_doserate_table') and self._doserate_table is not None:
            del self._doserate_table
            
        # 가비지 컬렉션 명시적 호출 (필요한 경우)
        if self.debug_mode:
            import gc
            gc.collect()
            self._log_memory_usage("자원 정리 후")

# # block
# file_path = r"C:\Users\com\OneDrive\2025 작업\MoQUI\Log_sample\Block\RP.101800 SONG JOON SOO - 2nd.dcm"

# MLC
# file_path = r"C:\Users\com\OneDrive\2025 작업\MoQUI\Log_sample\MLC\RP.102176 HAN JOON OO.dcm"
# file_path = r"C:\Users\com\Downloads\조광현 교수님 전달자료\Plan (dicom)\RP_G270_C090.dcm"

# file_path = r"C:\Users\com\OneDrive\2025 작업\Code_작성중\PTN_reader\비교\102256 KIM DONG IL\RP.102256 KIM DONG IL.dcm"
# file_path = r"C:\Users\breezing\OneDrive\2025 작업\Code_작성중\PTN_reader\비교\102256 KIM DONG IL\RP.102256 KIM DONG IL.dcm"

file_path = r"C:\Users\com\Downloads\SMC BOT 분석결과\Plan(dcm)\RP_G270_C090.dcm"

d1 = LineScanningPosWtMQ(file_path, debug_mode=True)
print(f"총 스캔 시간: {d1.result}")

BoT_layers = [layer.total_scan_time for layer in d1.ports[0].layers]
print(f"BoT_layers: {BoT_layers}")

layer_infos = []
# 데이터 수집
for i_layer, layer in enumerate(d1.ports[0].layers):
    layer_weights_data = []

    weight_seg = [segment.weight for segment in layer.line_segments]
    distance_seg = [segment.distance for segment in layer.line_segments]
    
    for i_segment, weight in enumerate(weight_seg):
        layer_weights_data.append({
            'Layer no': i_layer + 1,
            'Energy': layer.energy,
            'dose_rate': layer.layer_doserate,
            'scan_time': layer.line_segments[i_segment].rounded_scan_time,
            'speed': layer.line_segments[i_segment].speed,
            'distance': layer.line_segments[i_segment].distance,
            'Segment no': i_segment,
            'Weight': weight
            })

    tmp_doserate = []
    
    for i in range(1, len(weight_seg)):  # 인덱스 1부터 시작
        if distance_seg[i] > 0:  # 0으로 나누기 방지
            doserate_value = 2000 * weight_seg[i] / distance_seg[i]
            tmp_doserate.append(doserate_value)

    DReff = max(weight_seg)/(1.2*min(weight_seg[1:]))

    layer_infos.append({
        'Layer no': i_layer + 1,
        'Energy': layer.energy,
        'dose_rate': layer.layer_doserate,
        'scan_time': layer.total_scan_time,
        'doserate max': max(tmp_doserate),
        'doserate min': min(tmp_doserate),
        'doserate with DRusr 200': max(tmp_doserate)/200,
        'DReff': DReff,
        'doserate with DReff': max(tmp_doserate)/DReff,
        })
    # DataFrame 생성 및 CSV 저장
    df = pd.DataFrame(layer_weights_data)
    df.to_csv(f'layer_weights_{i_layer+1}.csv', index=False, encoding='utf-8-sig')

# DataFrame 생성 및 CSV 저장
df2 = pd.DataFrame(layer_infos)
df2.to_csv('layer_infos.csv', index=False, encoding='utf-8-sig')
print("CSV 파일이 저장되었습니다: layer_infos.csv")

# d1.cleanup_resources