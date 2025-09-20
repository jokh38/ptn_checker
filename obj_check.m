classdef obj_check
    %UNTITLED2 이 클래스의 요약 설명 위치
    %   자세한 설명 위치
    
    
    % Properties that correspond to obj components
    properties (Access = public)
        UIFigure              matlab.ui.Figure
        BTN_plan              matlab.ui.control.Button
        BTN_PTN               matlab.ui.control.Button
        BTN_CALC              matlab.ui.control.Button
        BTN_report            matlab.ui.control.Button
        BTN_reset             matlab.ui.control.Button
        Label2                matlab.ui.control.Label
        LabelLinearGauge      matlab.ui.control.Label
        ProgressBar           matlab.ui.control.LinearGauge
        LabelTextArea         matlab.ui.control.Label
        TextArea              matlab.ui.control.TextArea
        TabGroup              matlab.ui.container.TabGroup
        Tab_POS               matlab.ui.container.Tab
        IMG_PSCHECK           matlab.ui.control.UIAxes
        FieldSpinnerLabel     matlab.ui.control.Label
        SPN_field1            matlab.ui.control.Spinner
        LayerSpinnerLabel     matlab.ui.control.Label
        SPN_layer1            matlab.ui.control.Spinner
        Tab_Trend             matlab.ui.container.Tab
        IMG_SIGMA             matlab.ui.control.UIAxes
        FieldSpinner_2Label   matlab.ui.control.Label
        SPN_field3            matlab.ui.control.Spinner
        IMG_OFFSET            matlab.ui.control.UIAxes
        Tab_Histogram         matlab.ui.container.Tab
        IMG_HISTx             matlab.ui.control.UIAxes
        FieldSpinner_3Label   matlab.ui.control.Label
        SPN_field2            matlab.ui.control.Spinner
        LayerSpinner_2Label   matlab.ui.control.Label
        SPN_layer2            matlab.ui.control.Spinner
        IMG_HISTy             matlab.ui.control.UIAxes
        UITable               matlab.ui.control.Table
        PlaninformationPanel  matlab.ui.container.Panel
        MRNLabel              matlab.ui.control.Label
        TXT_MRN               matlab.ui.control.TextArea
        NameTextAreaLabel_2   matlab.ui.control.Label
        TXT_Name              matlab.ui.control.TextArea
        GantryLabel           matlab.ui.control.Label
        TXT_Gantry            matlab.ui.control.TextArea
    end
    
    
    properties (Access = private)
        MRN                          % Description
        plan_MRN
        plan_beamname
        
        field_list
        ptn_date_list
        filename_mgn
        filename_ptn
        filename_ptn_aday
        indx_gantry
        MGN
        PTN
        current_layerN
        current_fieldN
        lineseg_pos
        lineseg_MU
        lineseg_cum_MU
        lineseg_energy
        layer_histo_x
        layer_histo_y
        plan_NPort
        plan_NLayer
        histo_pos
        histo_stddev_x
        histo_offset_x
        histo_stddev_y
        histo_offset_y
        
    end
    
    methods (Static, Access = private)
        
        function w_real = F_SHI_spotW( temp_spot_x1, temp_spot_x2, temp_spot_x3, temp_spot_x4 )
            % declarations
            temp_spot_x1 = double(temp_spot_x1);
            temp_spot_x2 = double(temp_spot_x2);
            temp_spot_x3 = double(temp_spot_x3);
            temp_spot_x4 = double(temp_spot_x4);
            
            % calculator
            w_real = 2^(floor(temp_spot_x3/128))*4^(-64 + temp_spot_x4)*...
                (1/2 + rem(temp_spot_x3,128)/2^8 + temp_spot_x2/2^16 + temp_spot_x1/2^24);
        end
        
        function x_real = F_SHI_spotP( temp_spot_x1, temp_spot_x2 )
            % x2 = 64: positive / 192: negative
            % x2 = 64 + 1 or +2 or etc...
            
            % declarations
            temp_spot_x1 = int16(temp_spot_x1);
            temp_spot_x2 = int16(temp_spot_x2);
            
            det_pos_x1 = int16(0);
            det_pos_x2 = int16(0);
            
            sign_pos_x2 = sign(2^7 - int16(temp_spot_x2));
            det_pos_x3 = mod(temp_spot_x2, 2^6);
            
            if det_pos_x3 > 2^5
                det_pos_x2 = -1;
            else
                det_pos_x2 = det_pos_x3;
            end
            
            det_pos_x1 = 2^7 - int16(temp_spot_x1); % 2^7 is half value of x1
            % sign_pos_x1 = sign(det_pos_x1);
            ind_helper_x1 = 2^3 - ( 2*(det_pos_x2 + 1) + 1 ) + abs( 1 - idivide(temp_spot_x1,2^7) );
            slope_x1 = 2^ind_helper_x1;
            real_diff = det_pos_x1/(2^ind_helper_x1);
            
            x_real = sign_pos_x2*( 2^( 2*(det_pos_x2 + 1) ) - real_diff ) ;
        end
        
    end
    
    methods (Access = public)
        
        % Code that executes after component creation
        function startupFcn(obj)
            % initial value
            obj.current_fieldN = 1;
            obj.current_layerN = 1;
            obj.indx_gantry = 1;
            obj.TextArea.BackgroundColor = [1 1 1];
        end
        
        % Button pushed function: BTN_CALC
        function BTN_CALCButtonPushed(obj)
            obj.ProgressBar.Value = 0;
            obj.TextArea.BackgroundColor = [1 1 0];
            temp_bin = [-5:0.01:5];
            temp_fun = @(ftparm, testedgep) ftparm(1)*...
                exp( -0.5*(testedgep - ftparm(2)).*(testedgep - ftparm(2))/ftparm(3)^2 );
            ftparm0 = [0.1 0 1];
            options = optimoptions('lsqcurvefit', 'FunctionTolerance', 1e-8, 'MaxIterations', 4500);
            
            temp_count = 1;
            
            for ii = 1:obj.plan_NPort
                for jj = 1:obj.plan_NLayer(ii,1)
                    plan_MU = obj.lineseg_cum_MU{jj,ii}(:,1)/obj.lineseg_cum_MU{jj,ii}(end,1);
                    plan_x  = double(obj.lineseg_pos{jj,ii}(:,1));
                    plan_y  = double(obj.lineseg_pos{jj,ii}(:,2));
                    
                    ptn_MU = obj.PTN{jj,ii}(:,8)/obj.PTN{jj,ii}(end,8);
                    ptn_x  = obj.PTN{jj,ii}(:,6);
                    ptn_y  = obj.PTN{jj,ii}(:,7);
                    
                    plan_intpf_x = interp1(plan_MU', plan_x', ptn_MU);
                    plan_intpf_y = interp1(plan_MU', plan_y', ptn_MU);
                    
                    [temp_N_x, temp_edge] = ...
                        histcounts(plan_intpf_x, temp_bin, 'Normalization', 'probability');
                    [temp_N_y, temp_edge] = ...
                        histcounts(plan_intpf_y, temp_bin, 'Normalization', 'probability');
                    
                    % position difference between plan and ptn with bin: temp_bin.
                    obj.histo_pos{jj,ii}(1,:) = temp_N_x;
                    obj.histo_pos{jj,ii}(2,:) = temp_N_y;
                    
                    obj.layer_histo_x{jj,ii} = ...
                        lsqcurvefit(temp_fun, ftparm0, temp_bin(2:end)', temp_N_x', [0, -2, 0], [2, 2, 5], options);
                    obj.layer_histo_y{jj,ii} = ...
                        lsqcurvefit(temp_fun, ftparm0, temp_bin(2:end)', temp_N_y', [0, -2, 0], [2, 2, 5], options);
                    
                    obj.histo_stddev_x(jj,ii) = obj.layer_histo_x{jj,ii}(3);
                    obj.histo_offset_x(jj,ii) = obj.layer_histo_x{jj,ii}(2);
                    obj.histo_stddev_y(jj,ii) = obj.layer_histo_y{jj,ii}(3);
                    obj.histo_offset_y(jj,ii) = obj.layer_histo_y{jj,ii}(2);
                    
                    temp_count = temp_count + 1;
                    
                    obj.ProgressBar.Value = round(100*temp_count/sum(obj.plan_NLayer),0);
                end
            end
            
            obj.TextArea.BackgroundColor = [1 1 1];
            obj.TextArea.Value = 'Comutation complete!';
        end
        
        % Button pushed function: BTN_PTN
        function BTN_PTNButtonPushed(obj, event)
            obj.ProgressBar.Value = 0;
            
            obj.TextArea.BackgroundColor = [1 1 0];
            
            current_dir = pwd;
            directory_name = uigetdir(current_dir, 'Select the root directory of SHI data');
            
            cd([directory_name,'\plan'])
            obj.filename_mgn = dir('*.mgn');
            cd(current_dir)
            for ii = 1:length(obj.filename_mgn)
                list1(ii,1) = str2num(obj.filename_mgn(ii).name(17:19));
            end
            obj.field_list = (unique(list1));
            %             disp(obj.field_list)
            
            obj.MRN = obj.filename_mgn(1).name(4:11);
            
            cd([directory_name,'\Actual\Scanning'])
            obj.filename_ptn = dir('*.ptn');
            for ii = 1:length(obj.filename_ptn)
                list11(ii,1) = round(obj.filename_ptn(ii).datenum,0);
            end
            
            obj.ptn_date_list = unique(list11);
            indx_aday  = (list11 == obj.ptn_date_list(1));
            obj.filename_ptn_aday = obj.filename_ptn(indx_aday);
            cd(current_dir)
            
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
            
            obj.TextArea.Value = ['No. of MGN files: ' num2str(length(obj.filename_mgn))];
            
            for j = 1:length(obj.filename_mgn)
                file_ID_plan = fopen([directory_name, '\plan\', obj.filename_mgn(j,1).name]);
                temp_array1 = fread(file_ID_plan);
                % plan binary file
                
                temp_pos{j,1} = transpose(reshape(temp_array1, 14, length(temp_array1)/14));
                
                % field number classification
                kkk = find(str2num(obj.filename_mgn(j).name(17:19)) == obj.field_list);
                
                kkkj = str2num(obj.filename_mgn(j).name(21:23));
                %                 disp([num2str(j) ' / ' num2str(kkk) ' / ' num2str(kkkj) ': ' num2str(size(temp_pos{j,1},1))])
                
                LS_pos_mgn{kkkj,kkk}(:,1) = temp_pos{j,1}(:,1)*base_dig^3 +...
                    temp_pos{j,1}(:,2)*base_dig^2 + temp_pos{j,1}(:,3)*base_dig + temp_pos{j,1}(:,4);
                LS_pos_mgn{kkkj,kkk}(:,2) = mgn_conv(obj.indx_gantry,1)*( base_dig*temp_pos{j,1}(:, 9) + temp_pos{j,1}(:,10) - 2^15 );
                LS_pos_mgn{kkkj,kkk}(:,3) = mgn_conv(obj.indx_gantry,2)*( base_dig*temp_pos{j,1}(:,11) + temp_pos{j,1}(:,12) - 2^15 );
                
                %                 for ii = 1:size(temp_pos{j,1},1)   % plan binary file
                %                     %                     disp(num2str(obj.indx_gantry))
                %                     LS_pos_mgn{kkkj,kkk}(ii,1) = temp_pos{j,1}(ii,1) *...
                %                         base_dig^3 + temp_pos{j,1}(ii,2) * base_dig^2 + base_dig*temp_pos{j,1}(ii,3) + temp_pos{j,1}(ii,4);
                %                     LS_pos_mgn{kkkj,kkk}(ii,2) = ...
                %                         mgn_conv(obj.indx_gantry,1)*( base_dig*temp_pos{j,1}(ii, 9) + temp_pos{j,1}(ii,10) - 2^15 );
                %                     LS_pos_mgn{kkkj,kkk}(ii,3) = ...
                %                         mgn_conv(obj.indx_gantry,2)*( base_dig*temp_pos{j,1}(ii,11) + temp_pos{j,1}(ii,12) - 2^15 );
                %                 end
                
                
                obj.ProgressBar.Value = round(100*j/length(obj.filename_ptn_aday),0);
            end
            obj.MGN = LS_pos_mgn;
            %%%%%%%%%%%%%%%%%%%%%%%%%%       MGN file converting      %%%%%%%%%%%%%%%%%%%%%%%%%
            obj.ProgressBar.Value = 0;
            
            % PTN file converting
            LS_pos_ptn = cell(1,length(obj.field_list));
            kkk = 1;
            
            obj.TextArea.Value = ['No. of PTN files: ' num2str(length(obj.filename_ptn_aday))];
            
            %%%%%%%%%%%%%%%%%%%%%%%%%%       PTN file converting      %%%%%%%%%%%%%%%%%%%%%%%%%
            for j = 1:length(obj.filename_ptn_aday)
                % field number classification
                kkk = find(str2num(obj.filename_ptn_aday(j).name(16:18)) == obj.field_list);
                kkkj = str2num(obj.filename_ptn_aday(j).name(20:22));
                
                file_ID_meas = fopen([directory_name, '\Actual\Scanning\', obj.filename_ptn_aday(j,1).name]);
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
                
                obj.ProgressBar.Value = round(100*j/length(obj.filename_ptn_aday),0);
                
                %                 if mod(j,10) == 0
                %                     disp(['MEAS:', num2str(j)])
                %                 end
            end
            obj.PTN = LS_pos_ptn;
            %%%%%%%%%%%%%%%%%%%%%%%%%%       PTN file converting      %%%%%%%%%%%%%%%%%%%%%%%%%
            
            obj.TextArea.BackgroundColor = [1 1 1];
            obj.TextArea.Value = 'Log data is loaded.';
        end
        
        % Button pushed function: BTN_plan
        function BTN_planButtonPushed(obj, event)
            
            obj.TextArea.BackgroundColor = [1 1 0];
            
            RTion_name = uigetfile('*.dcm','Select DICOM RT ION file');
            
            
            d_header = dicominfo(RTion_name);
            temp_port_name = fieldnames(d_header.IonBeamSequence);
            N_port = length(temp_port_name); % number of radiation beam fields
            obj.SPN_field1.Limits = [1 N_port];
            obj.SPN_field2.Limits = [1 N_port];
            obj.SPN_field3.Limits = [1 N_port];
            
            obj.plan_NPort    = N_port;
            obj.plan_MRN      = d_header.PatientID;
            
            obj.TXT_Name.Value  = [d_header.PatientName.GivenName, '/', d_header.PatientName.FamilyName];
            eval(['obj.TXT_Gantry.Value = d_header.IonBeamSequence.',temp_port_name{1,1},'.TreatmentMachineName;'])
            
            if ismember('G1',obj.TXT_Gantry.Value) == [logical(1),logical(1)]
                obj.indx_gantry = 1;
            elseif ismember('G2',obj.TXT_Gantry.Value) == [logical(1),logical(1)]
                obj.indx_gantry = 2;
            else
                errordlg('Gantry cannot be determined.')
            end
            
            
            obj.TXT_MRN.Value = obj.plan_MRN;
            
            for k = 1:N_port
                eval(['obj.plan_beamname{k,1} = d_header.IonBeamSequence.',temp_port_name{k,1},'.BeamDescription;'])
                eval(['info_layer = d_header.IonBeamSequence.',temp_port_name{k,1},'.IonControlPointSequence;'])
                
                field_name_st = fieldnames(info_layer);
                N_fields = numel(field_name_st)/2; % number of layers
                obj.plan_NLayer(k,1) = N_fields;
                
                for i = 1:N_fields
                    jj = 2*(i-1)+1;
                    eval(['spot_info{i,1}(1,1) = info_layer.',field_name_st{jj,1},'.NominalBeamEnergy;'])
                    eval(['obj.lineseg_energy{i,k} = info_layer.',field_name_st{jj,1},'.NominalBeamEnergy;'])
                    eval(['spot_info{i,2}(1,1) = info_layer.',field_name_st{jj,1},'.CumulativeMetersetWeight;'])
                    eval(['spot_info{i,3}(1,1) = info_layer.',field_name_st{jj+1,1},'.CumulativeMetersetWeight;'])
                    
                    % (300B,1094): Line scan position map
                    eval(['t1 = info_layer.',field_name_st{jj,1},'.Private_300b_1094;'])
                    eval(['spot_info{i,4} = reshape(t1,[8,length(t1)/8]);'])
                    % (300B,1096): Line scan meterset weights
                    eval(['t2 = info_layer.',field_name_st{jj,1},'.Private_300b_1096;'])
                    eval(['spot_info{i,5} = reshape(t2,[4,length(t2)/4]);'])
                    
                    % (300B,1092): Number of line scan spot positions
                    eval(['spot_info{i,6} = info_layer.',field_name_st{jj,1},'.Private_300b_1092;'])
                    % (300B,1090): Line spot tune ID
                    eval(['spot_info{i,7} = info_layer.',field_name_st{jj,1},'.Private_300b_1090;'])
                end
                
                % ----------- Spot position and weight extraction -----------%
                for i = 1:length(spot_info) % number of layers
                    
                    temp_lineseg = zeros(1,1);
                    temp_lineseg_cumMU = zeros(1,1);
                    
                    for j = 1:size(spot_info{i,4},2) % spot position number
                        % x-position
                        obj.lineseg_pos{i,k}(j,1) = obj.F_SHI_spotP(spot_info{i,4}(3,j), spot_info{i,4}(4,j));
                        % y-position
                        obj.lineseg_pos{i,k}(j,2) = obj.F_SHI_spotP(spot_info{i,4}(7,j), spot_info{i,4}(8,j));
                        % weight
                        %  obj.lineseg_MU{i,1}(:,1) = obj.F_SHI_spotW( spot_info{i,5}(1,j), ...
                        %          spot_info{i,5}(2,j), spot_info{i,5}(3,j), spot_info{i,5}(4,j) );
                        
                        temp_lineseg(j,1) = obj.F_SHI_spotW( spot_info{i,5}(1,j), ...
                            spot_info{i,5}(2,j), spot_info{i,5}(3,j), spot_info{i,5}(4,j) );
                        if j == 1
                            temp_lineseg_cumMU(j,1) = temp_lineseg(j,1);
                        else
                            temp_lineseg_cumMU(j,1) = temp_lineseg(j,1) + temp_lineseg_cumMU(j-1,1);
                        end
                    end
                    temp_sum = sum(temp_lineseg(:,1));
                    obj.lineseg_MU{i,k}(:,1) = temp_lineseg(:,1)*...
                        (spot_info{i,3}(1) - spot_info{i,2}(1))/temp_sum;
                    obj.lineseg_cum_MU{i,k}(:,1) = temp_lineseg_cumMU(:,1)*...
                        (spot_info{i,3}(1) - spot_info{i,2}(1))/temp_sum;
                end
            end
            
            for ii = 1:N_port
                temp_tabledata{ii,1} = obj.plan_beamname{ii,1};
                temp_tabledata{ii,2} = obj.plan_NLayer(ii,1);
            end
            
            obj.TextArea.BackgroundColor = [1 1 1];
            obj.UITable.Data = temp_tabledata;
            obj.TextArea.Value = 'Plan data is loaded.';
        end
        
        
        
        %%%%%%%%%%%------------------------------------------%%%%%%%%%%%%
        
        
        
        
        % Button pushed function: BTN_reset
        function BTN_resetButtonPushed(obj, event)
            clear obj.MRN obj.plan_MRN obj.plan_beamname obj.field_list obj.ptn_date_list
            clear obj.filename_mgn obj.filename_ptn obj.filename_ptn_aday obj.indx_gantry
            clear obj.MGN obj.PTN obj.current_layerN obj.current_fieldN
            clear obj.lineseg_pos obj.lineseg_MU obj.lineseg_cum_MU obj.lineseg_energy
            clear obj.layer_histo_x obj.layer_histo_y obj.plan_NPort obj.plan_NLayer
            
            % initial value
            obj.current_fieldN = 1;
            obj.current_layerN = 1;
            obj.indx_gantry = 1;
            obj.TextArea.BackgroundColor = [1 1 1];
        end
        
        % Value changed function: SPN_field1
        function SPN_field1ValueChanged(obj, event)
            obj.current_fieldN = obj.SPN_field1.Value;
            obj.TextArea.Value = ['Current field: ' num2str(obj.current_fieldN) ];
            
            if obj.current_fieldN == 0
                errordlg('Enter the value in the field input box', 'Input error')
            end
        end
        
        % Value changing function: SPN_field1
        function SPN_field1ValueChanging(obj, event)
            obj.current_fieldN = event.Value;
            obj.SPN_layer1.Limits = [1 obj.plan_NLayer(obj.current_fieldN, 1)];
            obj.TextArea.Value = ['Current field: ' num2str(obj.current_fieldN) ];
            
            scatter(obj.IMG_PSCHECK, obj.PTN{obj.current_layerN,obj.current_fieldN}(:,6),...
                obj.PTN{obj.current_layerN,obj.current_fieldN}(:,7), 5, '+')
            hold(obj.IMG_PSCHECK);
            plot(obj.IMG_PSCHECK, obj.lineseg_pos{obj.current_layerN, obj.current_fieldN}(:,1), ...
                obj.lineseg_pos{obj.current_layerN,obj.current_fieldN}(:,2),'r','LineWidth',1)
            %             plot(obj.IMG_PSCHECK, obj.MGN{obj.current_layerN, obj.current_fieldN}(2:end-1,2), ...
            %                 obj.MGN{obj.current_layerN,obj.current_fieldN}(2:end-1,3),'r','LineWidth',1)
            legend(obj.IMG_PSCHECK, 'PLAN','LOG')
        end
        
        % Value changing function: SPN_field2
        function SPN_field2ValueChanging(obj, event)
            obj.current_fieldN = event.Value;
            obj.SPN_layer2.Limits = [1 obj.plan_NLayer(obj.current_fieldN, 1)];
            
            temp_bin = [-5:0.01:5];
            temp_fun = @(ftparm, testedgep) ftparm(1)*...
                exp( -0.5*(testedgep - ftparm(2)).*(testedgep - ftparm(2))/ftparm(3)^2 );
            
            plot(obj.IMG_HISTx, temp_bin(2:end), ...
                temp_fun(obj.layer_histo_x{obj.current_layerN, obj.current_fieldN}, temp_bin(2:end)), 'r', ...
                temp_bin(2:end), obj.histo_pos{obj.current_layerN, obj.current_fieldN}(1,:))
            plot(obj.IMG_HISTy, temp_bin(2:end), ...
                temp_fun(obj.layer_histo_y{obj.current_layerN, obj.current_fieldN}, temp_bin(2:end)), 'r',...
                temp_bin(2:end), obj.histo_pos{obj.current_layerN, obj.current_fieldN}(2,:))
            
            obj.TextArea.Value = num2str(obj.histo_pos{obj.current_layerN, obj.current_fieldN}(1,:));
            
        end
        
        % Value changed function: SPN_field3
        function SPN_field3ValueChanged(obj, event)
            obj.current_fieldN = obj.SPN_field3.Value;
            
            obj.TextArea.Value = ['Current field: ' num2str(obj.current_fieldN) ];
            
            temp_stddev_x = obj.histo_stddev_x(:,obj.current_fieldN);
            temp_offset_x = obj.histo_offset_x(:,obj.current_fieldN);
            temp_stddev_y = obj.histo_stddev_y(:,obj.current_fieldN);
            temp_offset_y = obj.histo_offset_y(:,obj.current_fieldN);
            
            temp_MUx = [1:obj.plan_NLayer(obj.current_fieldN,1)];
            
            plot(obj.IMG_SIGMA, temp_MUx, temp_stddev_x(1:length(temp_MUx)), 'b',...
                temp_MUx, temp_stddev_y(1:length(temp_MUx)) )
            legend(obj.IMG_SIGMA, 'X','Y')
            plot(obj.IMG_OFFSET, temp_MUx, temp_offset_x(1:length(temp_MUx)), 'b',...
                temp_MUx, temp_offset_y(1:length(temp_MUx)) )
            legend(obj.IMG_OFFSET, 'X','Y')
        end
        
        % Value changing function: SPN_field3
        function SPN_field3ValueChanging(obj, event)
            obj.current_fieldN = event.Value;
            obj.TextArea.Value = ['Current field: ' num2str(obj.current_fieldN) ];
            
            temp_stddev_x = obj.histo_stddev_x(:,obj.current_fieldN);
            temp_offset_x = obj.histo_offset_x(:,obj.current_fieldN);
            temp_stddev_y = obj.histo_stddev_y(:,obj.current_fieldN);
            temp_offset_y = obj.histo_offset_y(:,obj.current_fieldN);
            
            temp_MUx = [1:obj.plan_NLayer(obj.current_fieldN,1)];
            
            plot(obj.IMG_SIGMA, temp_MUx, temp_stddev_x(1:length(temp_MUx)), 'b',...
                temp_MUx, temp_stddev_y(1:length(temp_MUx)) )
            legend(obj.IMG_SIGMA, 'X','Y')
            plot(obj.IMG_OFFSET, temp_MUx, temp_offset_x(1:length(temp_MUx)), 'b',...
                temp_MUx, temp_offset_y(1:length(temp_MUx)) )
            legend(obj.IMG_OFFSET, 'X','Y')
        end
        
        % Value changed function: SPN_layer1
        function SPN_layer1ValueChanged(obj, event)
            obj.current_layerN = obj.SPN_layer1.Value;
            obj.TextArea.Value = ['Current layer: ' num2str(obj.current_layerN) ];
            
            if obj.current_layerN == 0
                errordlg('Enter the value in the layer input box', 'Input error')
            end
        end
        
        % Value changing function: SPN_layer1
        function SPN_layer1ValueChanging(obj, event)
            obj.current_layerN = event.Value;
            obj.TextArea.Value = ['Current layer: ' num2str(obj.current_layerN) ];
            
            
            scatter(obj.IMG_PSCHECK, obj.PTN{obj.current_layerN,obj.current_fieldN}(:,6),...
                obj.PTN{obj.current_layerN,obj.current_fieldN}(:,7), 5, '+')
            hold(obj.IMG_PSCHECK);
            plot(obj.IMG_PSCHECK, obj.lineseg_pos{obj.current_layerN, obj.current_fieldN}(:,1), ...
                obj.lineseg_pos{obj.current_layerN, obj.current_fieldN}(:,2), 'r', 'LineWidth',1)
            %             plot(obj.IMG_PSCHECK, obj.MGN{obj.current_layerN, obj.current_fieldN}(2:end-1,2), ...
            %                 obj.MGN{obj.current_layerN,obj.current_fieldN}(2:end-1,3),'r','LineWidth',1)
        end
        
        % Value changing function: SPN_layer2
        function SPN_layer2ValueChanging(obj, event)
            obj.current_layerN = event.Value;
            
            temp_bin = [-5:0.01:5];
            temp_fun = @(ftparm, testedgep) ftparm(1)*...
                exp( -0.5*(testedgep - ftparm(2)).*(testedgep - ftparm(2))/ftparm(3)^2 );
            
            plot(obj.IMG_HISTx, temp_bin(2:end), ...
                temp_fun(obj.layer_histo_x{obj.current_layerN, obj.current_fieldN}, temp_bin(2:end)), 'r', ...
                temp_bin(2:end), obj.histo_pos{obj.current_layerN, obj.current_fieldN}(1,:))
            plot(obj.IMG_HISTy, temp_bin(2:end), ...
                temp_fun(obj.layer_histo_y{obj.current_layerN, obj.current_fieldN}, temp_bin(2:end)), 'r',...
                temp_bin(2:end), obj.histo_pos{obj.current_layerN, obj.current_fieldN}(2,:))
            
        end
    end
    
    % obj initialization and construction
    methods (Access = private)
        
        % Create UIFigure and components
        function createComponents(obj)
            
            % Create UIFigure
            obj.UIFigure = uifigure;
            obj.UIFigure.Position = [101 101 766 612];
            obj.UIFigure.Name = 'UI Figure';
            
            % Create BTN_plan
            obj.BTN_plan = uibutton(obj.UIFigure, 'push');
            obj.BTN_plan.ButtonPushedFcn = createCallbackFcn(obj, @BTN_planButtonPushed, true);
            obj.BTN_plan.Position = [42.5 514 103 22];
            obj.BTN_plan.Text = '1. DICOM PLAN';
            
            % Create BTN_PTN
            obj.BTN_PTN = uibutton(obj.UIFigure, 'push');
            obj.BTN_PTN.ButtonPushedFcn = createCallbackFcn(obj, @BTN_PTNButtonPushed, true);
            obj.BTN_PTN.Position = [168 514 100 22];
            obj.BTN_PTN.Text = '2. PTN file';
            
            % Create BTN_CALC
            obj.BTN_CALC = uibutton(obj.UIFigure, 'push');
            obj.BTN_CALC.ButtonPushedFcn = createCallbackFcn(obj, @BTN_CALCButtonPushed, true);
            obj.BTN_CALC.Position = [45 479 100 22];
            obj.BTN_CALC.Text = '3. Calculation';
            
            % Create BTN_report
            obj.BTN_report = uibutton(obj.UIFigure, 'push');
            obj.BTN_report.Position = [167 479 100 22];
            obj.BTN_report.Text = 'Create report!';
            
            % Create BTN_reset
            obj.BTN_reset = uibutton(obj.UIFigure, 'push');
            obj.BTN_reset.ButtonPushedFcn = createCallbackFcn(obj, @BTN_resetButtonPushed, true);
            obj.BTN_reset.Position = [632 16 100 21];
            obj.BTN_reset.Text = 'Reset';
            
            % Create Label2
            obj.Label2 = uilabel(obj.UIFigure);
            obj.Label2.HorizontalAlignment = 'center';
            obj.Label2.FontSize = 28;
            obj.Label2.Position = [44 567 688 36];
            obj.Label2.Text = 'Spot position check (SMC)';
            
            % Create LabelLinearGauge
            obj.LabelLinearGauge = uilabel(obj.UIFigure);
            obj.LabelLinearGauge.HorizontalAlignment = 'center';
            obj.LabelLinearGauge.Position = [107 447 105 15];
            obj.LabelLinearGauge.Text = 'Computation status';
            
            % Create ProgressBar
            obj.ProgressBar = uigauge(obj.UIFigure, 'linear');
            obj.ProgressBar.Position = [41 410 238 35];
            
            % Create LabelTextArea
            obj.LabelTextArea = uilabel(obj.UIFigure);
            obj.LabelTextArea.HorizontalAlignment = 'right';
            obj.LabelTextArea.Position = [41 23 21 15];
            obj.LabelTextArea.Text = 'Log';
            
            % Create TextArea
            obj.TextArea = uitextarea(obj.UIFigure);
            obj.TextArea.Position = [71 16 294 28];
            
            % Create TabGroup
            obj.TabGroup = uitabgroup(obj.UIFigure);
            obj.TabGroup.Position = [296 71 460 489];
            
            % Create Tab_POS
            obj.Tab_POS = uitab(obj.TabGroup);
            obj.Tab_POS.Title = 'Line Seg. Position';
            
            % Create IMG_PSCHECK
            obj.IMG_PSCHECK = uiaxes(obj.Tab_POS);
            xlabel(obj.IMG_PSCHECK, 'X')
            ylabel(obj.IMG_PSCHECK, 'Y')
            obj.IMG_PSCHECK.Position = [6 34 446 425];
            
            % Create FieldSpinnerLabel
            obj.FieldSpinnerLabel = uilabel(obj.Tab_POS);
            obj.FieldSpinnerLabel.HorizontalAlignment = 'right';
            obj.FieldSpinnerLabel.Position = [98 17 32 15];
            obj.FieldSpinnerLabel.Text = 'Field';
            
            % Create SPN_field1
            obj.SPN_field1 = uispinner(obj.Tab_POS);
            obj.SPN_field1.ValueChangingFcn = createCallbackFcn(obj, @SPN_field1ValueChanging, true);
            obj.SPN_field1.ValueChangedFcn = createCallbackFcn(obj, @SPN_field1ValueChanged, true);
            obj.SPN_field1.Limits = [1 Inf];
            obj.SPN_field1.Position = [137 13 73 22];
            obj.SPN_field1.Value = 1;
            
            % Create LayerSpinnerLabel
            obj.LayerSpinnerLabel = uilabel(obj.Tab_POS);
            obj.LayerSpinnerLabel.HorizontalAlignment = 'right';
            obj.LayerSpinnerLabel.Position = [258 17 36 15];
            obj.LayerSpinnerLabel.Text = 'Layer';
            
            % Create SPN_layer1
            obj.SPN_layer1 = uispinner(obj.Tab_POS);
            obj.SPN_layer1.ValueChangingFcn = createCallbackFcn(obj, @SPN_layer1ValueChanging, true);
            obj.SPN_layer1.ValueChangedFcn = createCallbackFcn(obj, @SPN_layer1ValueChanged, true);
            obj.SPN_layer1.Limits = [1 Inf];
            obj.SPN_layer1.Position = [302 13 73 22];
            obj.SPN_layer1.Value = 1;
            
            % Create Tab_Trend
            obj.Tab_Trend = uitab(obj.TabGroup);
            obj.Tab_Trend.Title = 'Deviations';
            
            % Create IMG_SIGMA
            obj.IMG_SIGMA = uiaxes(obj.Tab_Trend);
            xlabel(obj.IMG_SIGMA, 'Layer No.')
            ylabel(obj.IMG_SIGMA, 'Std.dev (mm)')
            obj.IMG_SIGMA.Position = [11 245 438 210];
            
            % Create FieldSpinner_2Label
            obj.FieldSpinner_2Label = uilabel(obj.Tab_Trend);
            obj.FieldSpinner_2Label.HorizontalAlignment = 'right';
            obj.FieldSpinner_2Label.Position = [157 14 32 15];
            obj.FieldSpinner_2Label.Text = 'Field';
            
            % Create SPN_field3
            obj.SPN_field3 = uispinner(obj.Tab_Trend);
            obj.SPN_field3.ValueChangingFcn = createCallbackFcn(obj, @SPN_field3ValueChanging, true);
            obj.SPN_field3.ValueChangedFcn = createCallbackFcn(obj, @SPN_field3ValueChanged, true);
            obj.SPN_field3.Limits = [1 Inf];
            obj.SPN_field3.Position = [204 10 100 22];
            obj.SPN_field3.Value = 1;
            
            % Create IMG_OFFSET
            obj.IMG_OFFSET = uiaxes(obj.Tab_Trend);
            xlabel(obj.IMG_OFFSET, 'Layer No.')
            ylabel(obj.IMG_OFFSET, 'Offset (mm)')
            obj.IMG_OFFSET.Position = [11 39 438 202];
            
            % Create Tab_Histogram
            obj.Tab_Histogram = uitab(obj.TabGroup);
            obj.Tab_Histogram.Title = 'Histograms';
            
            % Create IMG_HISTx
            obj.IMG_HISTx = uiaxes(obj.Tab_Histogram);
            xlabel(obj.IMG_HISTx, 'X')
            ylabel(obj.IMG_HISTx, 'Y')
            obj.IMG_HISTx.Position = [6 254 446 205];
            
            % Create FieldSpinner_3Label
            obj.FieldSpinner_3Label = uilabel(obj.Tab_Histogram);
            obj.FieldSpinner_3Label.HorizontalAlignment = 'right';
            obj.FieldSpinner_3Label.Position = [98 17 32 15];
            obj.FieldSpinner_3Label.Text = 'Field';
            
            % Create SPN_field2
            obj.SPN_field2 = uispinner(obj.Tab_Histogram);
            obj.SPN_field2.ValueChangingFcn = createCallbackFcn(obj, @SPN_field2ValueChanging, true);
            obj.SPN_field2.Limits = [1 Inf];
            obj.SPN_field2.Position = [137 13 73 22];
            obj.SPN_field2.Value = 1;
            
            % Create LayerSpinner_2Label
            obj.LayerSpinner_2Label = uilabel(obj.Tab_Histogram);
            obj.LayerSpinner_2Label.HorizontalAlignment = 'right';
            obj.LayerSpinner_2Label.Position = [258 17 36 15];
            obj.LayerSpinner_2Label.Text = 'Layer';
            
            % Create SPN_layer2
            obj.SPN_layer2 = uispinner(obj.Tab_Histogram);
            obj.SPN_layer2.ValueChangingFcn = createCallbackFcn(obj, @SPN_layer2ValueChanging, true);
            obj.SPN_layer2.Limits = [1 Inf];
            obj.SPN_layer2.Position = [302 13 73 22];
            obj.SPN_layer2.Value = 1;
            
            % Create IMG_HISTy
            obj.IMG_HISTy = uiaxes(obj.Tab_Histogram);
            xlabel(obj.IMG_HISTy, 'X')
            ylabel(obj.IMG_HISTy, 'Y')
            obj.IMG_HISTy.Position = [7 50 446 205];
            
            % Create UITable
            obj.UITable = uitable(obj.UIFigure);
            obj.UITable.ColumnName = {'Name'; 'Layer No.'};
            obj.UITable.RowName = {};
            obj.UITable.Position = [37 71 245 160];
            
            % Create PlaninformationPanel
            obj.PlaninformationPanel = uipanel(obj.UIFigure);
            obj.PlaninformationPanel.Title = 'Plan information';
            obj.PlaninformationPanel.Position = [37 242 245 111];
            
            % Create MRNLabel
            obj.MRNLabel = uilabel(obj.PlaninformationPanel);
            obj.MRNLabel.HorizontalAlignment = 'right';
            obj.MRNLabel.Position = [9 69 33 15];
            obj.MRNLabel.Text = 'MRN';
            
            % Create TXT_MRN
            obj.TXT_MRN = uitextarea(obj.PlaninformationPanel);
            obj.TXT_MRN.Position = [57 67 182 19];
            
            % Create NameTextAreaLabel_2
            obj.NameTextAreaLabel_2 = uilabel(obj.PlaninformationPanel);
            obj.NameTextAreaLabel_2.HorizontalAlignment = 'right';
            obj.NameTextAreaLabel_2.Position = [6 43 38 15];
            obj.NameTextAreaLabel_2.Text = 'Name';
            
            % Create TXT_Name
            obj.TXT_Name = uitextarea(obj.PlaninformationPanel);
            obj.TXT_Name.Position = [59 41 182 19];
            
            % Create GantryLabel
            obj.GantryLabel = uilabel(obj.PlaninformationPanel);
            obj.GantryLabel.HorizontalAlignment = 'right';
            obj.GantryLabel.Position = [3 15 41 15];
            obj.GantryLabel.Text = 'Gantry';
            
            % Create TXT_Gantry
            obj.TXT_Gantry = uitextarea(obj.PlaninformationPanel);
            obj.TXT_Gantry.Position = [59 13 182 19];
        end
    end
    
    methods (Access = public)
        
        % Construct obj
        function obj = LS_pos_check_ver2
            
            % Create and configure components
            createComponents(obj)
            
            % Register the obj with obj Designer
            registerobj(obj, obj.UIFigure)
            
            % Execute the startup function
            runStartupFcn(obj, @startupFcn)
            
            if nargout == 0
                clear obj
            end
        end
        
        % Code that executes before obj deletion
        function delete(obj)
            
            % Delete UIFigure when obj is deleted
            delete(obj.UIFigure)
        end
    end
end