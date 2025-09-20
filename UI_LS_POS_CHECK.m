function varargout = UI_LS_POS_CHECK(varargin)
% UI_LS_POS_CHECK MATLAB code for UI_LS_POS_CHECK.fig
%      UI_LS_POS_CHECK, by itself, creates a new UI_LS_POS_CHECK or raises the existing
%      singleton*.
%
%      H = UI_LS_POS_CHECK returns the handle to a new UI_LS_POS_CHECK or the handle to
%      the existing singleton*.
%
%      UI_LS_POS_CHECK('CALLBACK',hObject,eventData,handles,...) calls the local
%      function named CALLBACK in UI_LS_POS_CHECK.M with the given input arguments.
%
%      UI_LS_POS_CHECK('Property','Value',...) creates a new UI_LS_POS_CHECK or raises
%      the existing singleton*.  Starting from the left, property value pairs are
%      applied to the GUI before UI_LS_POS_CHECK_OpeningFcn gets called.  An
%      unrecognized property name or invalid value makes property application
%      stop.  All inputs are passed to UI_LS_POS_CHECK_OpeningFcn via varargin.
%
%      *See GUI Options on GUIDE's Tools menu.  Choose "GUI allows only one
%      instance to run (singleton)".
%
% See also: GUIDE, GUIDATA, GUIHANDLES

% Edit the above text to modify the response to help UI_LS_POS_CHECK

% Last Modified by GUIDE v2.5 27-Sep-2017 14:18:31

% Begin initialization code - DO NOT EDIT
gui_Singleton = 1;
gui_State = struct('gui_Name',       mfilename, ...
                   'gui_Singleton',  gui_Singleton, ...
                   'gui_OpeningFcn', @UI_LS_POS_CHECK_OpeningFcn, ...
                   'gui_OutputFcn',  @UI_LS_POS_CHECK_OutputFcn, ...
                   'gui_LayoutFcn',  [] , ...
                   'gui_Callback',   []);
if nargin && ischar(varargin{1})
    gui_State.gui_Callback = str2func(varargin{1});
end

if nargout
    [varargout{1:nargout}] = gui_mainfcn(gui_State, varargin{:});
else
    gui_mainfcn(gui_State, varargin{:});
end
% End initialization code - DO NOT EDIT

% --- Executes just before UI_LS_POS_CHECK is made visible.
function UI_LS_POS_CHECK_OpeningFcn(hObject, eventdata, handles, varargin)
% This function has no output args, see OutputFcn.
% hObject    handle to figure
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    structure with handles and user data (see GUIDATA)
% varargin   command line arguments to UI_LS_POS_CHECK (see VARARGIN)

% Choose default command line output for UI_LS_POS_CHECK
handles.output = hObject;

% Update handles structure
guidata(hObject, handles);

initialize_gui(hObject, handles, false);

% UIWAIT makes UI_LS_POS_CHECK wait for user response (see UIRESUME)
% uiwait(handles.figure1);

% --- Outputs from this function are returned to the command line.
function varargout = UI_LS_POS_CHECK_OutputFcn(hObject, eventdata, handles)
% varargout  cell array for returning output args (see VARARGOUT);
% hObject    handle to figure
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    structure with handles and user data (see GUIDATA)

% Get default command line output from handles structure
varargout{1} = handles.output;

% --- Executes during object creation, after setting all properties.
function edtbox_fieldN_CreateFcn(hObject, eventdata, handles)
% hObject    handle to edtbox_fieldN (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    empty - handles not created until after all CreateFcns called

% Hint: popupmenu controls usually have a white background on Windows.
%       See ISPC and COMPUTER.
if ispc && isequal(get(hObject,'BackgroundColor'), get(0,'defaultUicontrolBackgroundColor'))
    set(hObject,'BackgroundColor','white');
end

function edtbox_fieldN_Callback(hObject, eventdata, handles)
% hObject    handle to edtbox_fieldN (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    structure with handles and user data (see GUIDATA)

% Hints: get(hObject,'String') returns contents of edtbox_fieldN as text
%        str2double(get(hObject,'String')) returns contents of edtbox_fieldN as a double

field_number = str2double(get(hObject, 'String'));

if isnan(field_number)
    set(hObject, 'String', 0);
    errordlg('Input must be a number','Error');
end

% Save the new edtbox_fieldN value
handles.inputdata.field_number = field_number;
guidata(hObject,handles)

% --- Executes during object creation, after setting all properties.
function edtbox_LayerN_CreateFcn(hObject, eventdata, handles)
% hObject    handle to edtbox_LayerN (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    empty - handles not created until after all CreateFcns called

% Hint: popupmenu controls usually have a white background on Windows.
%       See ISPC and COMPUTER.
if ispc && isequal(get(hObject,'BackgroundColor'), get(0,'defaultUicontrolBackgroundColor'))
    set(hObject,'BackgroundColor','white');
end

function edtbox_LayerN_Callback(hObject, eventdata, handles)
% hObject    handle to edtbox_LayerN (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    structure with handles and user data (see GUIDATA)

% Hints: get(hObject,'String') returns contents of edtbox_LayerN as text
%        str2double(get(hObject,'String')) returns contents of edtbox_LayerN as a double
Layer_number = str2double(get(hObject, 'String'));

if isnan(Layer_number)
    set(hObject, 'String', 0);
    errordlg('Input must be a number','Error');
end

% Save the new edtbox_LayerN value
set(handles.inputdata.Layer_number, 'String', Layer_number)
guidata(hObject,handles)

% --- Executes on button press in pshbtn_PTNdirectory.
function pshbtn_PTNdirectory_Callback(hObject, eventdata, handles)
% hObject    handle to pshbtn_PTNdirectory (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    structure with handles and user data (see GUIDATA)

current_dir = pwd;
directory_name = uigetdir(current_dir, 'Select the root directory of SHI data');

disp(directory_name)

cd([directory_name,'\plan'])
filename_mgn = dir('*.mgn');

cd(current_dir)
for ii = 1:length(filename_mgn)
    list1(ii,1) = str2num(filename_mgn(ii).name(17:19));
end

field_list = (unique(list1));

MRN = filename_mgn(1).name(4:11);

cd([directory_name,'\Actual\Scanning'])
filename_ptn = dir('*.ptn');
for ii = 1:length(filename_ptn)
    list11(ii,1) = round(filename_ptn(ii).datenum,0);
end

ptn_date_list = unique(list11);
indx_aday  = (list11 == ptn_date_list(1));
filename_ptn_aday = filename_ptn(indx_aday);
cd(current_dir)

set(handles.inputdata.directory_name, 'String', directory_name);
set(handles.processdata.MRN, 'String', MRN);
set(handles.processdata.fieldlist, 'String', field_list);
set(handles.processdata.MGNlist, 'String', filename_mgn);
set(handles.processdata.PTNlist, 'String', filename_ptn_aday);


% --- Executes on button press in pshbtn_Calculate.
function pshbtn_Calculate_Callback(hObject, eventdata, handles)
% hObject    handle to pshbtn_Calculate (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    structure with handles and user data (see GUIDATA)
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

temp_field_list = handles.processdata.fieldlist;

% MGN file converting
LS_pos_mgn = cell(1,length(temp_field_list));
%%%%%%%%%%%%%%%%%%%%%%%%%%       MGN file converting      %%%%%%%%%%%%%%%%%%%%%%%%%
kkk = 1;

for j = 1:length(handles.processdata.MGNlist)
    file_ID_plan = fopen([handles.inputdata.directory_name, '\plan\', handles.processdata.MGNlist(j,1).name]);
    temp_array1 = fread(file_ID_plan);
    % plan binary file
    
    temp_pos{j,1} = transpose(reshape(temp_array1, 14, length(temp_array1)/14));
    % field number classification
    kkk = find(str2num(handles.processdata.MGNlist(j).name(17:19)) == temp_field_list);
    kkkj = str2num(handles.processdata.MGNlist(j).name(21:23));
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
% obj.MGN = LS_pos_mgn;
set(handles.processdata.MGN, 'String', LS_pos_mgn);
%%%%%%%%%%%%%%%%%%%%%%%%%%       MGN file converting      %%%%%%%%%%%%%%%%%%%%%%%%%

% PTN file converting
LS_pos_ptn = cell(1,length(temp_field_list));
kkk = 1;
%%%%%%%%%%%%%%%%%%%%%%%%%%       PTN file converting      %%%%%%%%%%%%%%%%%%%%%%%%%
for j = 1:length(handles.processdata.PTNlist)
    % field number classification
    kkk = find(str2num(handles.processdata.PTNlist(j).name(16:18)) == temp_field_list);
    kkkj = str2num(handles.processdata.PTNlist(j).name(20:22));
    
    file_ID_meas = fopen([obj.directory_name, '\Actual\Scanning\', handles.processdata.PTNlist(j,1).name]);
    temp_array2 = fread(file_ID_meas);
    
    % record binary file
    temp_pos{j,2} = transpose(reshape(temp_array2, 16, length(temp_array2)/16));
    ipp = 1;
    for ii = 1:size(temp_pos{j,2},1) % record binary file
        if temp_pos{j,2}(ii,5) > 0
            LS_pos_ptn{kkkj,kkk}(ipp,1) = base_dig*temp_pos{j,2}(ii,1) + temp_pos{j,2}(ii,2); % x position
            LS_pos_ptn{kkkj,kkk}(ipp,2) = base_dig*temp_pos{j,2}(ii,3) + temp_pos{j,2}(ii,4); % y position
            LS_pos_ptn{kkkj,kkk}(ipp,3) = base_dig*temp_pos{j,2}(ii,5) + temp_pos{j,2}(ii,6); % x spot size
            LS_pos_ptn{kkkj,kkk}(ipp,4) = base_dig*temp_pos{j,2}(ii,7) + temp_pos{j,2}(ii,8); % y spot size
            LS_pos_ptn{kkkj,kkk}(ipp,5) = base_dig*temp_pos{j,2}(ii,9) + temp_pos{j,2}(ii,10); % MU delivered
            LS_pos_ptn{kkkj,kkk}(ipp,6) = ptn_slope(obj.indx_gantry,1)*LS_pos_ptn{kkkj,kkk}(ipp,1) +...
                ptn_conv{obj.indx_gantry,1}(1,1) - 1.5;
            LS_pos_ptn{kkkj,kkk}(ipp,7) = ptn_slope(obj.indx_gantry,2)*LS_pos_ptn{kkkj,kkk}(ipp,2) + ...
                ptn_conv{obj.indx_gantry,1}(2,1) - 1.8 ;
            ipp = ipp + 1;
        end
    end
    if mod(j,10) == 0
        disp(['MEAS:', num2str(j)])
    end
end
% obj.PTN = LS_pos_ptn;
set(handles.processdata.PTN, 'String', LS_pos_ptn);
%%%%%%%%%%%%%%%%%%%%%%%%%%       PTN file converting      %%%%%%%%%%%%%%%%%%%%%%%%%

% set(handles.processdata.MRNlist, 'String', MRN);
% set(handles.processdata.PTNlist, 'String', filename_ptn_aday);


% --- Executes on button press in pshbtn_reset.
function pshbtn_reset_Callback(hObject, eventdata, handles)
% hObject    handle to pshbtn_reset (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    structure with handles and user data (see GUIDATA)

initialize_gui(gcbf, handles, true);

% --- Executes when selected object changed in unitgroup.
function unitgroup_SelectionChangedFcn(hObject, eventdata, handles)
% hObject    handle to the selected object in unitgroup 
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    structure with handles and user data (see GUIDATA)

if (hObject == handles.radbtn_G1)
    set(handles.inputdata.gantry_Num, 'String', 1);
else
    set(handles.inputdata.gantry_Num, 'String', 2);
end

% --------------------------------------------------------------------
function initialize_gui(fig_handle, handles, isreset)
% If the metricdata field is present and the pshbtn_reset flag is false, it means
% we are we are just re-initializing a GUI by calling it from the cmd line
% while it is up. So, bail out as we dont want to pshbtn_reset the data.
if isfield(handles, 'metricdata') && ~isreset
    return;
end

handles.inputdata.field_number = 0;
handles.inputdata.Layer_number = 0;

set(handles.edtbox_fieldN, 'String', handles.inputdata.field_number);
set(handles.edtbox_LayerN, 'String', handles.inputdata.Layer_number);

handles.inputdata.gantry_Num

% set(handles.unitgroup, 'SelectedObject', handles.radbtn_G1);
% set(handles.unitgroup, 'SelectedObject', handles.radbtn_G2);
% set(handles.unitgroup, 'SelectedObject', handles.radbtn_RTIONPLAN);
% set(handles.unitgroup, 'SelectedObject', handles.radbtn_MGN);

% Update handles structure
guidata(handles.figure1, handles);

% --- Executes on button press in pshbtn_report.
function pshbtn_report_Callback(hObject, eventdata, handles)
% hObject    handle to pshbtn_report (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    structure with handles and user data (see GUIDATA)

% --- Executes on button press in pshbtn_dicomRTionplan.
function pshbtn_dicomRTionplan_Callback(hObject, eventdata, handles)
% hObject    handle to pshbtn_dicomRTionplan (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    structure with handles and user data (see GUIDATA)

% --- Executes during object creation, after setting all properties.
function radbtn_G1_CreateFcn(hObject, eventdata, handles)
% hObject    handle to radbtn_G1 (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    empty - handles not created until after all CreateFcns called


% --- Executes on button press in radbtn_G1.
function radbtn_G1_Callback(hObject, eventdata, handles)
% hObject    handle to radbtn_G1 (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    structure with handles and user data (see GUIDATA)
% Save the new edtbox_fieldN value
% Hint: get(hObject,'Value') returns toggle state of radbtn_G1


% --- Executes on button press in radbtn_G2.
function radbtn_G2_Callback(hObject, eventdata, handles)
% hObject    handle to radbtn_G2 (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    structure with handles and user data (see GUIDATA)
% Save the new edtbox_fieldN value
% Hint: get(hObject,'Value') returns toggle state of radbtn_G2


% --- Executes on button press in radbtn_RTIONPLAN.
function radbtn_RTIONPLAN_Callback(hObject, eventdata, handles)
% hObject    handle to radbtn_RTIONPLAN (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    structure with handles and user data (see GUIDATA)
% Hint: get(hObject,'Value') returns toggle state of radbtn_RTIONPLAN


% --- Executes on button press in radbtn_MGN.
function radbtn_MGN_Callback(hObject, eventdata, handles)
% hObject    handle to radbtn_MGN (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    structure with handles and user data (see GUIDATA)
% Hint: get(hObject,'Value') returns toggle state of radbtn_MGN


% --- Executes when selected object is changed in uibuttongroup3.
function uibuttongroup3_SelectionChangedFcn(hObject, eventdata, handles)
% hObject    handle to the selected object in uibuttongroup3 
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    structure with handles and user data (see GUIDATA)
if (hObject == handles.radbtn_RTIONPLAN)
    set(handles.inputdata.PLAN_sel, 'String', 'DICOM');
else
    set(handles.inputdata.PLAN_sel, 'String', 'MGN');
end
