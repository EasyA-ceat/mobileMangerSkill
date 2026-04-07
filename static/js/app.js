const { createApp, ref, reactive, onMounted, onUnmounted } = Vue;
const { ElMessage, ElMessageBox } = ElementPlus;

const app = createApp({
    setup() {
        const API_BASE = '';

        const devices = ref([]);
        const currentDevice = ref(null);
        const currentScreenshot = ref(null);
        const activeTab = ref('screen');
        const connected = ref(false);
        const inputText = ref('');
        const scripts = ref([]);
        const logs = ref([]);
        const recording = ref(false);
        const recordingStatus = ref(null);
        const recordedScript = ref(null);
        const showCreateScript = ref(false);
        const showSaveScript = ref(false);

        const newScript = reactive({
            script_name: '',
            description: '',
            script_content: ''
        });

        const saveScriptForm = reactive({
            script_name: '',
            description: ''
        });

        const logFilter = reactive({
            device_id: null
        });

        let ws = null;
        let recordingTimer = null;

        const refreshDevices = async () => {
            try {
                const response = await fetch(`${API_BASE}/api/v1/devices`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ refresh: true })
                });
                const data = await response.json();
                if (data.code === 0) {
                    devices.value = data.data.devices || [];
                    ElMessage.success('设备列表刷新成功');
                } else {
                    ElMessage.error(data.message);
                }
            } catch (error) {
                ElMessage.error('刷新设备列表失败: ' + error.message);
            }
        };

        const selectDevice = (device) => {
            currentDevice.value = device;
            connected.value = device.status === 'connected';
            currentScreenshot.value = null;
            refreshScripts();
            refreshLogs();
            ElMessage.success(`已选择设备: ${device.name || device.device_id}`);
        };

        const takeScreenshot = async () => {
            if (!currentDevice.value) {
                ElMessage.warning('请先选择一个设备');
                return;
            }
            try {
                const response = await fetch(`${API_BASE}/api/v1/devices/${currentDevice.value.device_id}/screenshot`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                });
                const data = await response.json();
                if (data.code === 0 && data.data.image_base64) {
                    currentScreenshot.value = 'data:image/png;base64,' + data.data.image_base64;
                    ElMessage.success('截图成功');
                } else {
                    ElMessage.error(data.message);
                }
            } catch (error) {
                ElMessage.error('截图失败: ' + error.message);
            }
        };

        const refreshScreen = () => {
            takeScreenshot();
        };

        const handleScreenClick = (event) => {
            if (!currentScreenshot.value || !currentDevice.value) {
                return;
            }
            const img = event.target;
            const rect = img.getBoundingClientRect();
            const x = Math.round((event.clientX - rect.left) * (img.naturalWidth / rect.width));
            const y = Math.round((event.clientY - rect.top) * (img.naturalHeight / rect.height));
            clickAt(x, y);
        };

        const clickAt = async (x, y) => {
            if (!currentDevice.value) {
                ElMessage.warning('请先选择一个设备');
                return;
            }
            try {
                const response = await fetch(`${API_BASE}/api/v1/devices/${currentDevice.value.device_id}/tap`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ target: `${x},${y}` })
                });
                const data = await response.json();
                if (data.code === 0) {
                    ElMessage.success('点击成功');
                    setTimeout(refreshScreen, 500);
                } else {
                    ElMessage.error(data.message);
                }
            } catch (error) {
                ElMessage.error('点击失败: ' + error.message);
            }
        };

        const pressKey = async (key) => {
            if (!currentDevice.value) {
                ElMessage.warning('请先选择一个设备');
                return;
            }
            try {
                const response = await fetch(`${API_BASE}/api/v1/devices/${currentDevice.value.device_id}/key`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ key: key })
                });
                const data = await response.json();
                if (data.code === 0) {
                    ElMessage.success('按键成功');
                    setTimeout(refreshScreen, 500);
                } else {
                    ElMessage.error(data.message);
                }
            } catch (error) {
                ElMessage.error('按键失败: ' + error.message);
            }
        };

        const sendInput = async () => {
            if (!currentDevice.value) {
                ElMessage.warning('请先选择一个设备');
                return;
            }
            if (!inputText.value.trim()) {
                ElMessage.warning('请输入要发送的文字');
                return;
            }
            try {
                const response = await fetch(`${API_BASE}/api/v1/devices/${currentDevice.value.device_id}/input`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ text: inputText.value })
                });
                const data = await response.json();
                if (data.code === 0) {
                    ElMessage.success('发送成功');
                    inputText.value = '';
                    setTimeout(refreshScreen, 500);
                } else {
                    ElMessage.error(data.message);
                }
            } catch (error) {
                ElMessage.error('发送失败: ' + error.message);
            }
        };

        const swipe = async (direction) => {
            if (!currentDevice.value) {
                ElMessage.warning('请先选择一个设备');
                return;
            }
            let start, end;
            switch (direction) {
                case 'up':
                    start = '500,1500';
                    end = '500,500';
                    break;
                case 'down':
                    start = '500,500';
                    end = '500,1500';
                    break;
                case 'left':
                    start = '900,1000';
                    end = '100,1000';
                    break;
                case 'right':
                    start = '100,1000';
                    end = '900,1000';
                    break;
            }
            try {
                const response = await fetch(`${API_BASE}/api/v1/devices/${currentDevice.value.device_id}/swipe`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ start: start, end: end, duration: 500 })
                });
                const data = await response.json();
                if (data.code === 0) {
                    ElMessage.success('滑动成功');
                    setTimeout(refreshScreen, 500);
                } else {
                    ElMessage.error(data.message);
                }
            } catch (error) {
                ElMessage.error('滑动失败: ' + error.message);
            }
        };

        const refreshScripts = async () => {
            try {
                const response = await fetch(`${API_BASE}/api/v1/scripts`);
                const data = await response.json();
                if (data.code === 0) {
                    scripts.value = data.data.scripts || [];
                }
            } catch (error) {
                console.error('刷新脚本列表失败:', error);
            }
        };

        const createScript = async () => {
            if (!newScript.script_name.trim()) {
                ElMessage.warning('请输入脚本名称');
                return;
            }
            try {
                const response = await fetch(`${API_BASE}/api/v1/scripts`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(newScript)
                });
                const data = await response.json();
                if (data.code === 0) {
                    ElMessage.success('脚本创建成功');
                    showCreateScript.value = false;
                    Object.assign(newScript, { script_name: '', description: '', script_content: '' });
                    refreshScripts();
                } else {
                    ElMessage.error(data.message);
                }
            } catch (error) {
                ElMessage.error('创建脚本失败: ' + error.message);
            }
        };

        const executeScript = async (script) => {
            if (!currentDevice.value) {
                ElMessage.warning('请先选择一个设备');
                return;
            }
            try {
                const response = await fetch(`${API_BASE}/api/v1/scripts/${script.id}/execute?device_id=${currentDevice.value.device_id}`, {
                    method: 'POST'
                });
                const data = await response.json();
                if (data.code === 0) {
                    ElMessage.success(`脚本执行完成: 成功${data.data.successful}个, 失败${data.data.failed}个`);
                    setTimeout(refreshScreen, 500);
                } else {
                    ElMessage.error(data.message);
                }
            } catch (error) {
                ElMessage.error('执行脚本失败: ' + error.message);
            }
        };

        const deleteScript = async (script) => {
            try {
                await ElMessageBox.confirm('确定要删除这个脚本吗?', '提示', {
                    confirmButtonText: '确定',
                    cancelButtonText: '取消',
                    type: 'warning'
                });
                const response = await fetch(`${API_BASE}/api/v1/scripts/${script.id}`, {
                    method: 'DELETE'
                });
                const data = await response.json();
                if (data.code === 0) {
                    ElMessage.success('脚本删除成功');
                    refreshScripts();
                } else {
                    ElMessage.error(data.message);
                }
            } catch (error) {
                if (error !== 'cancel') {
                    ElMessage.error('删除脚本失败: ' + error.message);
                }
            }
        };

        const startRecording = async () => {
            if (!currentDevice.value) {
                ElMessage.warning('请先选择一个设备');
                return;
            }
            try {
                const response = await fetch(`${API_BASE}/api/v1/record/start`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ device_id: currentDevice.value.device_id })
                });
                const data = await response.json();
                if (data.code === 0) {
                    recording.value = true;
                    recordingStatus.value = data.data;
                    ElMessage.success('开始录制');
                    recordingTimer = setInterval(updateRecordingStatus, 1000);
                } else {
                    ElMessage.error(data.message);
                }
            } catch (error) {
                ElMessage.error('开始录制失败: ' + error.message);
            }
        };

        const stopRecording = async () => {
            try {
                const response = await fetch(`${API_BASE}/api/v1/record/stop?device_id=${currentDevice.value?.device_id || ''}`, {
                    method: 'POST'
                });
                const data = await response.json();
                if (data.code === 0) {
                    recording.value = false;
                    if (recordingTimer) {
                        clearInterval(recordingTimer);
                        recordingTimer = null;
                    }
                    recordedScript.value = data.data.script_json;
                    ElMessage.success('停止录制');
                } else {
                    ElMessage.error(data.message);
                }
            } catch (error) {
                ElMessage.error('停止录制失败: ' + error.message);
            }
        };

        const updateRecordingStatus = async () => {
            try {
                const response = await fetch(`${API_BASE}/api/v1/record/status?device_id=${currentDevice.value?.device_id || ''}`);
                const data = await response.json();
                if (data.code === 0) {
                    recordingStatus.value = data.data;
                }
            } catch (error) {
                console.error('更新录制状态失败:', error);
            }
        };

        const saveRecordedScript = () => {
            saveScriptForm.script_name = `录制脚本_${new Date().toLocaleString()}`;
            saveScriptForm.description = '';
            showSaveScript.value = true;
        };

        const confirmSaveScript = async () => {
            if (!saveScriptForm.script_name.trim()) {
                ElMessage.warning('请输入脚本名称');
                return;
            }
            try {
                const response = await fetch(`${API_BASE}/api/v1/scripts`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        script_name: saveScriptForm.script_name,
                        description: saveScriptForm.description,
                        script_content: recordedScript.value
                    })
                });
                const data = await response.json();
                if (data.code === 0) {
                    ElMessage.success('脚本保存成功');
                    showSaveScript.value = false;
                    recordedScript.value = null;
                    refreshScripts();
                } else {
                    ElMessage.error(data.message);
                }
            } catch (error) {
                ElMessage.error('保存脚本失败: ' + error.message);
            }
        };

        const refreshLogs = async () => {
            try {
                let url = `${API_BASE}/api/v1/logs?limit=100`;
                if (logFilter.device_id) {
                    url += `&device_id=${logFilter.device_id}`;
                }
                const response = await fetch(url);
                const data = await response.json();
                if (data.code === 0) {
                    logs.value = data.data.logs || [];
                }
            } catch (error) {
                console.error('刷新日志失败:', error);
            }
        };

        const connectWebSocket = () => {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/ws`;
            ws = new WebSocket(wsUrl);

            ws.onopen = () => {
                console.log('WebSocket连接成功');
                if (currentDevice.value) {
                    ws.send(JSON.stringify({
                        type: 'subscribe',
                        device_id: currentDevice.value.device_id
                    }));
                }
            };

            ws.onmessage = (event) => {
                try {
                    const message = JSON.parse(event.data);
                    console.log('收到WebSocket消息:', message);
                } catch (error) {
                    console.error('解析WebSocket消息失败:', error);
                }
            };

            ws.onclose = () => {
                console.log('WebSocket连接关闭');
                setTimeout(connectWebSocket, 3000);
            };

            ws.onerror = (error) => {
                console.error('WebSocket错误:', error);
            };
        };

        onMounted(() => {
            refreshDevices();
            refreshScripts();
            refreshLogs();
            connectWebSocket();
        });

        onUnmounted(() => {
            if (ws) {
                ws.close();
            }
            if (recordingTimer) {
                clearInterval(recordingTimer);
            }
        });

        for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
            app.component(key, component);
        }

        return {
            devices,
            currentDevice,
            currentScreenshot,
            activeTab,
            connected,
            inputText,
            scripts,
            logs,
            recording,
            recordingStatus,
            recordedScript,
            showCreateScript,
            showSaveScript,
            newScript,
            saveScriptForm,
            logFilter,
            refreshDevices,
            selectDevice,
            takeScreenshot,
            refreshScreen,
            handleScreenClick,
            pressKey,
            sendInput,
            swipe,
            refreshScripts,
            createScript,
            executeScript,
            deleteScript,
            startRecording,
            stopRecording,
            saveRecordedScript,
            confirmSaveScript,
            refreshLogs
        };
    }
});

app.use(ElementPlus);
app.mount('#app');
