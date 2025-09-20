classdef LS_PosCheck_ver2 < handle
    %UNTITLED 이 클래스의 요약 설명 위치
    %   자세한 설명 위치
    
    properties
        PLAN = struct();
        MGN  = struct();
        PTN  = struct();
        indx_gantry
        MRN
        directory_name
        filename_mgn
        filename_ptn
        filename_ptn_aday
        field_list
        ptn_date_list
        PTN_allday_trigger = 0;
    end
    
    methods
        function F_Read_filename(obj)
            % directory_name = 'C:\Users\jokh38\OneDrive\2017 작업\Scanning pattern maker\G2_SCAN\37856798\1\';
            current_dir = pwd;
            obj.directory_name = uigetdir(current_dir, 'Select the root directory of SHI data');
            
            cd([obj.directory_name,'\plan'])
            obj.filename_mgn = dir('*.mgn');
            cd(current_dir)
            for ii = 1:length(obj.filename_mgn)
                list1(ii,1) = str2num(obj.filename_mgn(ii).name(17:19));
            end
            obj.field_list = (unique(list1));
            
            obj.MRN = obj.filename_mgn(1).name(4:11);
            
            cd([obj.directory_name,'\Actual\Scanning'])
            obj.filename_ptn = dir('*.ptn');
            for ii = 1:length(obj.filename_ptn)
                list11(ii,1) = round(obj.filename_ptn(ii).datenum,0);
            end
            
            obj.ptn_date_list = unique(list11);
            indx_aday  = (list11 == obj.ptn_date_list(1));
            obj.filename_ptn_aday = obj.filename_ptn(indx_aday);
            cd(current_dir)
        end
        
        function F_Pos_Conv(obj) % Converting binary data to position data from.
            % Start function
            base_dig = 2^8;
            mgn_conv = [0.0054705 0.0058206; 0.005445 0.0071411];
            
            % for G1: ptn_conv{1,1} = [x_min x_max; y_min y_max] real value
            % for G1: ptn_conv{1,2} = [x_max y_max] binary value
            ptn_conv{1,1} = [-176.747 182.347; -187.749 193.698];
            ptn_conv{1,2} = [2^15-1 2^15-1];
            ptn_slope(1,1) = ( ptn_conv{1,1}(1,2) - ptn_conv{1,1}(1,1) )/ptn_conv{1,2}(1); % x
            ptn_slope(1,2) = ( ptn_conv{1,1}(2,2) - ptn_conv{1,1}(2,1) )/ptn_conv{1,2}(2); % y
            
            % for G2: ptn_conv{2,1} = [x_min x_max; y_min y_max] real value
            % for G2: ptn_conv{2,2} = [x_max y_max] binary value
            ptn_conv{2,1} = [-176.563 180.273; -232.171 235.821];
            ptn_conv{2,2} = [3*2^14-2 2^16-1];
            ptn_slope(2,1) = ( ptn_conv{2,1}(1,2) - ptn_conv{2,1}(1,1) )/ptn_conv{2,2}(1);
            ptn_slope(2,2) = ( ptn_conv{2,1}(2,2) - ptn_conv{2,1}(2,1) )/ptn_conv{2,2}(2);
            
            % MGN file converting
            LS_pos_mgn = cell(1,length(obj.field_list));
            %%%%%%%%%%%%%%%%%%%%%%%%%%       MGN file converting      %%%%%%%%%%%%%%%%%%%%%%%%%
            kkk = 1;
            
            for j = 1:length(obj.filename_mgn)
                file_ID_plan = fopen([obj.directory_name, '\plan\', obj.filename_mgn(j,1).name]);
                temp_array1 = fread(file_ID_plan);
                % plan binary file
                
                temp_pos{j,1} = transpose(reshape(temp_array1, 14, length(temp_array1)/14));                
                % field number classification
                kkk = find(str2num(obj.filename_mgn(j).name(17:19)) == obj.field_list);
                kkkj = str2num(obj.filename_mgn(j).name(21:23));                
%                 disp([num2str(j) ' / ' num2str(kkk) ' / ' num2str(kkkj) ': ' num2str(size(temp_pos{j,1},1))])
                
                for ii = 1:size(temp_pos{j,1},1)   % plan binary file                    
                    LS_pos_mgn{kkkj,kkk}(ii,1) = temp_pos{j,1}(ii,1) * base_dig^3 + ... 
                        temp_pos{j,1}(ii,2) * base_dig^2 + base_dig*temp_pos{j,1}(ii,3) + temp_pos{j,1}(ii,4);
                    LS_pos_mgn{kkkj,kkk}(ii,2) = mgn_conv(obj.indx_gantry,1)*...
                        ( base_dig*temp_pos{j,1}(ii, 9) + temp_pos{j,1}(ii,10) - 2^15 );
                    LS_pos_mgn{kkkj,kkk}(ii,3) = mgn_conv(obj.indx_gantry,2)*...
                        ( base_dig*temp_pos{j,1}(ii,11) + temp_pos{j,1}(ii,12) - 2^15 );
                end
                
                if mod(j,10) == 0
                    disp(['PLAN:', num2str(j)])
                end
            end
            obj.MGN = LS_pos_mgn;
            %%%%%%%%%%%%%%%%%%%%%%%%%%       MGN file converting      %%%%%%%%%%%%%%%%%%%%%%%%%
            
            % PTN file converting
            LS_pos_ptn = cell(1,length(obj.field_list));;
            kkk = 1;
            %%%%%%%%%%%%%%%%%%%%%%%%%%       PTN file converting      %%%%%%%%%%%%%%%%%%%%%%%%%
            for j = 1:length(obj.filename_ptn_aday)
                % field number classification
                kkk = find(str2num(obj.filename_ptn_aday(j).name(16:18)) == obj.field_list);
                kkkj = str2num(obj.filename_ptn_aday(j).name(20:22));
                
                file_ID_meas = fopen([obj.directory_name, '\Actual\Scanning\', obj.filename_ptn_aday(j,1).name]);
                temp_array2 = fread(file_ID_meas);
                
                % record binary file
                temp_pos_ptn = transpose(reshape(temp_array2, 16, length(temp_array2)/16));
                
                temp_pos_ptn_real = temp_pos_ptn(temp_pos_ptn(:,5) > 0, :);                
                for ii = 1:5
                    % 1: x / 2: y / 3: x-spot / 4: y-spot / 5: MU
                    LS_pos_ptn{kkkj,kkk}(:,ii) = base_dig*temp_pos_ptn_real(:, 2*ii-1) + temp_pos_ptn_real(:, 2*ii);
                end
                
                LS_pos_ptn{kkkj,kkk}(:,6) = ptn_slope(obj.indx_gantry,1)*LS_pos_ptn{kkkj,kkk}(:,1) +...
                    ptn_conv{obj.indx_gantry,1}(1,1) - 1.2;
                LS_pos_ptn{kkkj,kkk}(:,7) = ptn_slope(obj.indx_gantry,2)*LS_pos_ptn{kkkj,kkk}(:,2) + ...
                    ptn_conv{obj.indx_gantry,1}(2,1) - 1.8 ;
                LS_pos_ptn{kkkj,kkk}(:,8) = cumsum(LS_pos_ptn{kkkj,kkk}(:,5));
                
                
                
                
%                 ipp = 1;
%                 for ii = 1:size(temp_pos_ptn,1) % record binary file
%                     if temp_pos_ptn(ii,5) > 0
%                         LS_pos_ptn{kkkj,kkk}(ipp,1) = base_dig*temp_pos_ptn(ii,1) + temp_pos_ptn(ii,2); % x position
%                         LS_pos_ptn{kkkj,kkk}(ipp,2) = base_dig*temp_pos_ptn(ii,3) + temp_pos_ptn(ii,4); % y position
%                         LS_pos_ptn{kkkj,kkk}(ipp,3) = base_dig*temp_pos_ptn(ii,5) + temp_pos_ptn(ii,6); % x spot size
%                         LS_pos_ptn{kkkj,kkk}(ipp,4) = base_dig*temp_pos_ptn(ii,7) + temp_pos_ptn(ii,8); % y spot size
%                         LS_pos_ptn{kkkj,kkk}(ipp,5) = base_dig*temp_pos_ptn(ii,9) + temp_pos_ptn(ii,10); % MU delivered
%                         LS_pos_ptn{kkkj,kkk}(ipp,6) = ptn_slope(obj.indx_gantry,1)*LS_pos_ptn{kkkj,kkk}(ipp,1) +...
%                             ptn_conv{obj.indx_gantry,1}(1,1) - 1.2;
%                         LS_pos_ptn{kkkj,kkk}(ipp,7) = ptn_slope(obj.indx_gantry,2)*LS_pos_ptn{kkkj,kkk}(ipp,2) + ...
%                             ptn_conv{obj.indx_gantry,1}(2,1) - 1.8 ;                        
%                        
%                         if ipp == 1
%                             LS_pos_ptn{kkkj,kkk}(ipp,8) = LS_pos_ptn{kkkj,kkk}(ipp,5);
%                         else
%                             LS_pos_ptn{kkkj,kkk}(ipp,8) = LS_pos_ptn{kkkj,kkk}(ipp-1,8) + LS_pos_ptn{kkkj,kkk}(ipp,5);
%                         end
%                         
%                         ipp = ipp + 1;
%                     end
%                 end
                
                
                
                
                
                if mod(j,10) == 0
                    disp(['MEAS:', num2str(j)])
                end
            end
            
            obj.PTN = LS_pos_ptn;
            %%%%%%%%%%%%%%%%%%%%%%%%%%       PTN file converting      %%%%%%%%%%%%%%%%%%%%%%%%%            
        end
        
        
    end
end

