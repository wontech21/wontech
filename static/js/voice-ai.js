/**
 * Voice AI Dashboard Assistant — "Talk to Your Business"
 * WebRTC connection to OpenAI Realtime API with function calling.
 */
(function () {
    'use strict';

    // -----------------------------------------------------------------------
    // State
    // -----------------------------------------------------------------------
    const State = { IDLE: 'idle', CONNECTING: 'connecting', LISTENING: 'listening', THINKING: 'thinking', SPEAKING: 'speaking' };
    let state = State.IDLE;
    let pc = null;           // RTCPeerConnection
    let dc = null;           // DataChannel
    let localStream = null;  // MediaStream from mic
    let audioEl = null;      // <audio> for remote playback
    let voiceAudioCtx = null; // AudioContext for speech bandpass filter

    // DOM refs (set in init)
    let btnMic, panel, statusDot, statusText, transcript, aiResponse, btnClose, btnPause, waveform, dataEl;
    let paused = false;

    // Tracks whether user started a new turn — used to clear stale viz
    let newUserTurn = false;

    // Tracks in-flight function calls — prevents response.done from
    // flipping to LISTENING while we're still awaiting fetch results.
    let activeFunctionCalls = 0;

    // Tracks the active response lifecycle. response.create must not be sent
    // while a response is still in progress — OpenAI rejects it.
    // responseDone resolves when response.done fires for the current response.
    let responseDone = Promise.resolve();
    let resolveResponseDone = null;

    // Browser speech recognition for real-time transcript display
    let recognition = null;

    // Chart.js state
    let activeCharts = [];
    const CHART_COLORS = [
        'rgba(99, 102, 241, 0.85)',   // indigo
        'rgba(16, 185, 129, 0.85)',   // emerald
        'rgba(245, 158, 11, 0.85)',   // amber
        'rgba(239, 68, 68, 0.85)',    // red
        'rgba(139, 92, 246, 0.85)',   // violet
        'rgba(6, 182, 212, 0.85)',    // cyan
        'rgba(236, 72, 153, 0.85)',   // pink
        'rgba(251, 191, 36, 0.85)',   // yellow
    ];
    const CHART_COLORS_FILL = [
        'rgba(99, 102, 241, 0.15)',
        'rgba(16, 185, 129, 0.15)',
        'rgba(245, 158, 11, 0.15)',
        'rgba(239, 68, 68, 0.15)',
        'rgba(139, 92, 246, 0.15)',
        'rgba(6, 182, 212, 0.15)',
        'rgba(236, 72, 153, 0.15)',
        'rgba(251, 191, 36, 0.15)',
    ];

    // -----------------------------------------------------------------------
    // Pretty header names — backend keys → polished display labels
    // -----------------------------------------------------------------------
    const HEADER_MAP = {
        // Identifiers
        'id': '#', 'order_id': 'Order', 'invoice_id': 'Invoice', 'employee_id': 'Employee',
        'item_id': 'Item', 'product_id': 'Product', 'recipe_id': 'Recipe', 'category_id': 'Category',
        'supplier_id': 'Supplier', 'schedule_id': 'Schedule',
        // Names
        'employee_name': 'Employee', 'supplier_name': 'Supplier', 'product_name': 'Product',
        'item_name': 'Item', 'category_name': 'Category', 'brand_name': 'Brand',
        'ingredient_name': 'Ingredient', 'recipe_name': 'Recipe', 'customer_name': 'Customer',
        'name': 'Name', 'full_name': 'Name', 'first_name': 'First Name', 'last_name': 'Last Name',
        // Financial
        'total': 'Total', 'subtotal': 'Subtotal', 'tax': 'Tax', 'tip': 'Tip', 'tips': 'Tips',
        'total_value': 'Total Value', 'total_spend': 'Total Spend', 'total_cost': 'Total Cost',
        'unit_price': 'Unit Price', 'price': 'Price', 'cost': 'Cost', 'amount': 'Amount',
        'gross_pay': 'Gross Pay', 'net_pay': 'Net Pay', 'regular_wages': 'Regular Pay',
        'ot_wages': 'Overtime Pay', 'revenue': 'Revenue', 'profit': 'Profit', 'margin': 'Margin',
        'discount': 'Discount', 'balance': 'Balance', 'payment_amount': 'Payment',
        // Hours / Time
        'total_hours': 'Total Hours', 'regular_hours': 'Regular Hrs', 'ot_hours': 'Overtime Hrs',
        'hours_worked': 'Hours Worked', 'clock_in': 'Clock In', 'clock_out': 'Clock Out',
        'start_time': 'Start', 'end_time': 'End', 'shift_start': 'Shift Start', 'shift_end': 'Shift End',
        'created_at': 'Created', 'updated_at': 'Updated', 'date': 'Date', 'week_start': 'Week Of',
        // Inventory
        'quantity': 'Qty', 'qty': 'Qty', 'stock_qty': 'In Stock', 'reorder_level': 'Reorder At',
        'unit': 'Unit', 'unit_of_measure': 'Unit', 'par_level': 'Par Level',
        'on_hand': 'On Hand', 'min_stock': 'Min Stock',
        // Status / Type
        'status': 'Status', 'order_status': 'Status', 'payment_status': 'Payment',
        'payment_method': 'Method', 'order_type': 'Type', 'type': 'Type',
        'department': 'Department', 'position': 'Position', 'role': 'Role',
        // Counts
        'total_items': 'Items', 'unique_ingredients': 'Ingredients', 'supplier_count': 'Suppliers',
        'alert_count': 'Alerts', 'order_count': 'Orders', 'item_count': 'Items',
        'inventory_value': 'Inventory Value',
        // Contact
        'email': 'Email', 'phone': 'Phone', 'address': 'Address',
        // Analytics
        'avg_order': 'Avg Order', 'avg_ticket': 'Avg Ticket',
        'frequency': 'Frequency', 'volatility': 'Volatility', 'variance': 'Variance',
        'trend': 'Trend', 'change': 'Change', 'growth': 'Growth',
    };

    function prettifyHeader(raw) {
        if (!raw || typeof raw !== 'string') return '';
        // Direct map hit
        const lower = raw.toLowerCase();
        if (HEADER_MAP[lower]) return HEADER_MAP[lower];
        // snake_case → Title Case
        return raw
            .replace(/_/g, ' ')
            .replace(/\b\w/g, c => c.toUpperCase())
            .replace(/\bId\b/g, '#')
            .replace(/\bOt\b/g, 'OT')
            .replace(/\bQty\b/g, 'Qty')
            .replace(/\bHrs\b/g, 'Hrs');
    }

    // Prettify badge keys too — "orders" → "Orders", "by_category" → "Categories"
    const BADGE_MAP = {
        'orders': 'Orders', 'employees': 'Employees', 'schedules': 'Shifts',
        'attendance': 'Records', 'pay_period': 'Pay Periods', 'items': 'Items',
        'by_category': 'Categories', 'invoices': 'Invoices', 'products': 'Products',
        'recipes': 'Recipes', 'ingredients': 'Ingredients', 'suppliers': 'Suppliers',
    };

    function prettifyBadge(key, count) {
        return `${count} ${BADGE_MAP[key] || prettifyHeader(key)}`;
    }

    // -----------------------------------------------------------------------
    // Route mapping — (toolName, queryType) → API URL builder
    // -----------------------------------------------------------------------
    function todayStr() { return new Date().toISOString().split('T')[0]; }
    function dateParams(a, fromKey, toKey) {
        const p = new URLSearchParams();
        if (a[fromKey || 'date_from']) p.set(fromKey === 'start_date' ? 'start_date' : 'date_from', a[fromKey || 'date_from']);
        if (a[toKey || 'date_to']) p.set(toKey === 'end_date' ? 'end_date' : 'date_to', a[toKey || 'date_to']);
        return p.toString();
    }

    const ROUTES = {
        query_sales: {
            orders_by_date:       a => `/api/pos/orders?date=${a.date || todayStr()}${a.status ? '&status=' + a.status : ''}`,
            sales_history:        () => `/api/sales/history`,
            sales_summary:        () => `/api/sales/summary`,
            sales_overview:       a => `/api/analytics/sales-overview?${dateParams(a, 'start_date', 'end_date') || `start_date=${todayStr()}&end_date=${todayStr()}`}`,
            product_sales_details:a => `/api/analytics/product-details?product_name=${encodeURIComponent(a.product_name || '')}&${dateParams(a, 'start_date', 'end_date')}`,
            time_comparison:      a => `/api/analytics/time-comparison?${dateParams(a, 'start_date', 'end_date')}`,
            sales_by_order_type:  a => `/api/analytics/sales-by-order-type?${dateParams(a, 'start_date', 'end_date')}`,
        },
        query_inventory: {
            summary:              () => `/api/inventory/summary`,
            detailed:             a => { const p = new URLSearchParams(); if (a.category) p.set('category', a.category); if (a.supplier) p.set('supplier', a.supplier); if (a.brand) p.set('brand', a.brand); if (a.date_from) p.set('date_from', a.date_from); if (a.date_to) p.set('date_to', a.date_to); return `/api/inventory/detailed?${p}`; },
            aggregated:           () => `/api/inventory/aggregated`,
            consolidated:         a => { const p = new URLSearchParams(); if (a.category) p.set('category', a.category); if (a.supplier) p.set('supplier', a.supplier); if (a.brand) p.set('brand', a.brand); return `/api/inventory/consolidated?${p}`; },
            products:             () => `/api/products/all`,
            product_costs:        () => `/api/products/costs`,
            recipes:              () => `/api/recipes/all`,
            recipe_for_product:   a => `/api/recipes/by-product/${encodeURIComponent(a.product_name || '')}`,
            ingredients_list:     () => `/api/ingredients/list`,
            categories:           () => `/api/categories/all`,
            brands:               () => `/api/brands/list`,
        },
        query_suppliers: {
            supplier_list:        () => `/api/suppliers/all`,
            vendor_spend:         a => `/api/analytics/vendor-spend?${dateParams(a)}`,
            supplier_performance: a => `/api/analytics/supplier-performance?${dateParams(a)}`,
            category_spending:    a => `/api/analytics/category-spending?${dateParams(a)}`,
        },
        query_invoices: {
            unreconciled:         () => `/api/invoices/unreconciled`,
            recent:               () => `/api/invoices/recent`,
            invoice_details:      a => `/api/invoices/${encodeURIComponent(a.invoice_number || '')}`,
            invoice_activity:     a => `/api/analytics/invoice-activity?${dateParams(a)}`,
        },
        query_employees: {
            list:                 () => `/api/employees`,
            details:              a => `/api/employees/${a.employee_id}`,
        },
        query_schedule: {
            schedules:            a => { const p = new URLSearchParams(); const d = a.date || todayStr(); p.set('start_date', a.start_date || d); p.set('end_date', a.end_date || d); if (a.employee_id) p.set('employee_id', a.employee_id); if (a.department) p.set('department', a.department); if (a.position) p.set('position', a.position); return `/api/schedules?${p}`; },
            time_off_requests:    a => { const p = new URLSearchParams(); if (a.employee_id) p.set('employee_id', a.employee_id); if (a.status) p.set('status', a.status); if (a.start_date) p.set('start_date', a.start_date); if (a.end_date) p.set('end_date', a.end_date); return `/api/schedules/time-off-requests?${p}`; },
        },
        query_attendance: {
            current_status:       () => `/api/attendance/status`,
            history:              a => `/api/attendance/history?date_from=${a.date_from || todayStr()}&date_to=${a.date_to || todayStr()}`,
        },
        query_payroll: {
            weekly:               a => `/api/payroll/weekly${a.week_start ? '?week_start=' + a.week_start : ''}`,
            monthly:              a => `/api/payroll/monthly?month=${a.month || new Date().getMonth() + 1}&year=${a.year || new Date().getFullYear()}`,
            summary:              a => { const p = new URLSearchParams(); if (a.start_date) p.set('start_date', a.start_date); if (a.end_date) p.set('end_date', a.end_date); return `/api/payroll/summary?${p}`; },
        },
        query_analytics: {
            summary:                    a => `/api/analytics/summary?${dateParams(a)}`,
            price_trends:               () => `/api/analytics/price-trends`,
            purchase_frequency:         () => `/api/analytics/purchase-frequency`,
            price_volatility:           () => `/api/analytics/price-volatility`,
            cost_variance:              () => `/api/analytics/cost-variance`,
            usage_forecast:             () => `/api/analytics/usage-forecast`,
            recipe_cost_trajectory:     () => `/api/analytics/recipe-cost-trajectory`,
            substitution_opportunities: () => `/api/analytics/substitution-opportunities`,
            dead_stock:                 a => `/api/analytics/dead-stock${a.days ? '?days=' + a.days : ''}`,
            eoq_optimizer:              () => `/api/analytics/eoq-optimizer`,
            seasonal_patterns:          () => `/api/analytics/seasonal-patterns`,
            menu_engineering:           () => `/api/analytics/menu-engineering`,
            waste_shrinkage:            () => `/api/analytics/waste-shrinkage`,
            inventory_value:            () => `/api/analytics/inventory-value`,
        },
        query_pos: {
            kitchen:              () => `/api/pos/kitchen`,
            register:             () => `/api/pos/register/current`,
            product_availability: () => `/api/pos/product-availability`,
            eighty_sixed:         () => `/api/pos/86-groups`,
            order_details:        a => `/api/pos/orders/${a.order_id}`,
            customer_lookup:      a => { const p = new URLSearchParams(); if (a.phone) p.set('phone', a.phone); if (a.name) p.set('name', a.name); return `/api/pos/customers/lookup?${p}`; },
        },
        query_menu: {
            hours:                () => `/api/menu-admin/hours`,
            settings:             () => `/api/menu-admin/settings`,
            categories:           () => `/api/menu-admin/categories`,
            items:                () => `/api/products/all`,
            modifier_groups:      a => a.item_id ? `/api/menu-admin/items/${a.item_id}/modifier-groups` : `/api/menu-admin/modifier-groups`,
        },
    };

    // -----------------------------------------------------------------------
    // Initialization
    // -----------------------------------------------------------------------
    function init() {
        btnMic      = document.getElementById('voice-ai-btn');
        panel       = document.getElementById('voice-ai-panel');
        statusDot   = document.getElementById('voice-ai-status-dot');
        statusText  = document.getElementById('voice-ai-status-text');
        transcript  = document.getElementById('voice-ai-transcript');
        aiResponse  = document.getElementById('voice-ai-response');
        btnClose    = document.getElementById('voice-ai-close');
        btnPause    = document.getElementById('voice-ai-pause');
        waveform    = document.getElementById('voice-ai-waveform');
        dataEl      = document.getElementById('voice-ai-data');

        if (!btnMic) return; // Voice AI not rendered (employee role)

        btnMic.addEventListener('click', toggleVoice);
        btnClose.addEventListener('click', stopVoice);
        if (btnPause) btnPause.addEventListener('click', togglePause);

        // Escape key to close
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && state !== State.IDLE) {
                stopVoice();
            }
        });

        // Create hidden audio element for remote playback
        audioEl = document.createElement('audio');
        audioEl.autoplay = true;
        document.body.appendChild(audioEl);
    }

    // -----------------------------------------------------------------------
    // Toggle (start / stop)
    // -----------------------------------------------------------------------
    function toggleVoice() {
        if (state === State.IDLE) {
            startVoice();
        } else {
            stopVoice();
        }
    }

    // -----------------------------------------------------------------------
    // Start — get ephemeral token, open WebRTC
    // -----------------------------------------------------------------------
    async function startVoice() {
        setState(State.CONNECTING);
        panel.classList.add('open');
        document.body.style.overflow = 'hidden';
        transcript.textContent = '';
        aiResponse.textContent = '';

        try {
            // 1. Get ephemeral client secret from our backend
            const tokenResp = await fetch('/api/voice/session', { method: 'POST' });
            const tokenData = await tokenResp.json();
            if (!tokenData.success) {
                showError(tokenData.error || 'Failed to create voice session');
                resetConnection();
                return;
            }

            // 2. Set up WebRTC peer connection
            pc = new RTCPeerConnection();

            // Handle remote audio from OpenAI
            pc.ontrack = (e) => {
                audioEl.srcObject = e.streams[0];
            };

            // 3. Get microphone with noise filtering constraints
            localStream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl: true,
                }
            });

            // 3b. Apply bandpass filter to isolate human speech frequencies (80Hz–3kHz)
            const audioCtx = new AudioContext();
            const source = audioCtx.createMediaStreamSource(localStream);
            const highpass = audioCtx.createBiquadFilter();
            highpass.type = 'highpass';
            highpass.frequency.value = 80;
            highpass.Q.value = 0.7;
            const lowpass = audioCtx.createBiquadFilter();
            lowpass.type = 'lowpass';
            lowpass.frequency.value = 3000;
            lowpass.Q.value = 0.7;
            const dest = audioCtx.createMediaStreamDestination();
            source.connect(highpass).connect(lowpass).connect(dest);
            voiceAudioCtx = audioCtx;

            pc.addTrack(dest.stream.getTracks()[0], dest.stream);

            // 4. Create data channel for events
            dc = pc.createDataChannel('oai-events');
            dc.onopen = () => {
                // Configure session with VAD via data channel
                dc.send(JSON.stringify({
                    type: 'session.update',
                    session: {
                        turn_detection: {
                            type: 'server_vad',
                            threshold: 0.7,
                            prefix_padding_ms: 300,
                            silence_duration_ms: 1000,
                        },
                    }
                }));
                setState(State.LISTENING);
                startRecognition();
            };
            dc.onmessage = handleDataChannelMessage;
            dc.onerror = (e) => {
                console.error('Voice AI data channel error:', e);
                showError('Connection error');
                stopVoice();
            };

            // 5. Create SDP offer (implicit) and send to OpenAI
            await pc.setLocalDescription();

            const sdpResp = await fetch('https://api.openai.com/v1/realtime?model=gpt-realtime', {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${tokenData.client_secret}`,
                    'Content-Type': 'application/sdp',
                },
                body: pc.localDescription.sdp,
            });

            if (!sdpResp.ok) {
                showError('Failed to connect to OpenAI Realtime');
                resetConnection();
                return;
            }

            // 6. Set remote description
            const answerSdp = await sdpResp.text();
            await pc.setRemoteDescription({ type: 'answer', sdp: answerSdp });

        } catch (err) {
            console.error('Voice AI start error:', err);
            if (err.name === 'NotAllowedError') {
                showError('Microphone access denied. Please allow mic access and try again.');
            } else {
                showError(err.message || 'Failed to start voice assistant');
            }
            resetConnection();
        }
    }

    // -----------------------------------------------------------------------
    // Reset connection but keep panel open (for showing errors)
    // -----------------------------------------------------------------------
    function resetConnection() {
        stopRecognition();
        if (localStream) {
            localStream.getTracks().forEach(t => t.stop());
            localStream = null;
        }
        if (voiceAudioCtx) { voiceAudioCtx.close(); voiceAudioCtx = null; }
        if (dc) { dc.close(); dc = null; }
        if (pc) { pc.close(); pc = null; }
        if (audioEl) audioEl.srcObject = null;
        setState(State.IDLE);
    }

    // -----------------------------------------------------------------------
    // Browser SpeechRecognition — live transcript while user speaks
    // -----------------------------------------------------------------------
    function startRecognition() {
        const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!SR) return;
        recognition = new SR();
        recognition.continuous = true;
        recognition.interimResults = true;
        recognition.lang = 'en-US';
        recognition.onresult = (e) => {
            // Only update while user is actively speaking, not during AI playback
            if (state !== State.LISTENING && state !== State.THINKING) return;
            let text = '';
            for (let i = e.resultIndex; i < e.results.length; i++) {
                text += e.results[i][0].transcript;
            }
            if (text) transcript.textContent = text;
        };
        // SpeechRecognition stops on its own sometimes — restart if session active
        recognition.onend = () => {
            if (state !== State.IDLE) {
                try { recognition.start(); } catch {}
            }
        };
        recognition.onerror = () => {}; // no-speech / aborted are normal
        try { recognition.start(); } catch {}
    }

    function stopRecognition() {
        if (recognition) {
            try { recognition.abort(); } catch {}
            recognition = null;
        }
    }

    // -----------------------------------------------------------------------
    // Stop — tear down everything
    // -----------------------------------------------------------------------
    function stopVoice() {
        stopRecognition();
        destroyActiveCharts();
        if (localStream) {
            localStream.getTracks().forEach(t => t.stop());
            localStream = null;
        }
        if (dc) {
            dc.close();
            dc = null;
        }
        if (pc) {
            pc.close();
            pc = null;
        }
        if (audioEl) {
            audioEl.srcObject = null;
        }
        panel.classList.remove('open');
        document.body.style.overflow = '';
        setPaused(false);
        setState(State.IDLE);
    }

    // -----------------------------------------------------------------------
    // Pause / Resume — mute mic + silence playback for reading time
    // -----------------------------------------------------------------------
    function togglePause() {
        setPaused(!paused);
    }

    function setPaused(val) {
        paused = val;
        // Mute/unmute mic track
        if (localStream) {
            localStream.getTracks().forEach(t => { t.enabled = !paused; });
        }
        // Mute/unmute AI audio playback
        if (audioEl) {
            audioEl.muted = paused;
        }
        // Stop browser speech recognition while paused
        if (paused) {
            stopRecognition();
        } else if (state !== State.IDLE) {
            startRecognition();
        }
        // Visual state
        if (btnPause) {
            btnPause.classList.toggle('paused', paused);
            btnPause.title = paused ? 'Resume listening' : 'Pause listening';
            btnPause.querySelector('.pause-icon').style.display = paused ? 'none' : '';
            btnPause.querySelector('.play-icon').style.display = paused ? '' : 'none';
        }
        // Update status text when paused (restore on resume)
        if (paused) {
            statusText.textContent = 'Paused';
            waveform.classList.remove('active');
        } else if (state !== State.IDLE) {
            setState(state); // refresh status text + waveform
        }
    }

    // -----------------------------------------------------------------------
    // Data channel message handler
    // -----------------------------------------------------------------------
    function handleDataChannelMessage(event) {
        let msg;
        try {
            msg = JSON.parse(event.data);
        } catch {
            return;
        }

        switch (msg.type) {
            // User started speaking — flag new turn, clear text only.
            // Viz is NOT cleared here because speaker echo/feedback can
            // trigger VAD and wipe freshly rendered charts.
            case 'input_audio_buffer.speech_started':
                newUserTurn = true;
                transcript.textContent = '';
                aiResponse.textContent = '';
                // Clear old viz when user speaks. Guard: only if LISTENING
                // (not SPEAKING), so speaker echo doesn't wipe fresh charts.
                if (state === State.LISTENING) {
                    destroyActiveCharts();
                    dataEl.innerHTML = '';
                }
                break;

            // User's speech transcribed
            case 'conversation.item.input_audio_transcription.completed':
                if (msg.transcript) {
                    transcript.textContent = msg.transcript;
                }
                break;

            // Model started generating a response
            case 'response.created':
                responseDone = new Promise(r => { resolveResponseDone = r; });
                setState(State.THINKING);
                break;

            // Audio response streaming — model is speaking
            case 'response.audio.delta':
                if (state !== State.SPEAKING) setState(State.SPEAKING);
                break;

            // Text delta from model — first real text in a new turn
            // clears stale viz. Echo rarely produces transcript text,
            // and create_visualization resets the flag before this fires,
            // so charts survive the spoken summary that follows them.
            case 'response.audio_transcript.delta':
                if (msg.delta) {
                    if (newUserTurn) {
                        destroyActiveCharts();
                        dataEl.innerHTML = '';
                        newUserTurn = false;
                    }
                    aiResponse.textContent += msg.delta;
                }
                break;

            // Response fully done — resolve the promise so queued response.create
            // calls can proceed. Only go to LISTENING if no function calls in flight.
            case 'response.done':
                if (resolveResponseDone) {
                    resolveResponseDone();
                    resolveResponseDone = null;
                }
                if (state !== State.IDLE && activeFunctionCalls === 0) {
                    setState(State.LISTENING);
                }
                break;

            // Model wants to call a function
            case 'response.function_call_arguments.done':
                handleFunctionCall(msg.call_id, msg.name, msg.arguments);
                break;

            // Error from OpenAI
            case 'error':
                console.error('Voice AI error:', msg.error);
                showError(msg.error?.message || 'An error occurred');
                break;
        }
    }

    // -----------------------------------------------------------------------
    // Function call handler — route lookup table → fetch → return result
    // -----------------------------------------------------------------------
    async function handleFunctionCall(callId, functionName, argsStr) {
        activeFunctionCalls++;
        setState(State.THINKING);

        try {
            let args = {};
            try { args = JSON.parse(argsStr || '{}'); } catch { args = {}; }

            // create_visualization — AI-driven chart rendering, no API call needed
            if (functionName === 'create_visualization') {
                destroyActiveCharts();
                dataEl.innerHTML = '';
                renderVisualization(args);
                newUserTurn = false; // chart is from THIS turn — don't let speech clear it
                await responseDone; // wait for current response to finish
                if (dc && dc.readyState === 'open') {
                    dc.send(JSON.stringify({
                        type: 'conversation.item.create',
                        item: {
                            type: 'function_call_output',
                            call_id: callId,
                            output: JSON.stringify({ success: true, rendered: args.chart_type, title: args.title })
                        }
                    }));
                    dc.send(JSON.stringify({ type: 'response.create' }));
                }
                return;
            }

            let result;
            try {
                if (functionName.startsWith('manage_')) {
                const resp = await fetch('/api/voice/action', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ action: functionName, params: args }),
                });
                result = await resp.json();
            } else if (functionName === 'run_sql_query') {
                    console.log('Voice SQL:', args.sql);
                    const resp = await fetch('/api/voice/query', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ sql: args.sql }),
                    });
                    result = await resp.json();
                    if (!result.success) console.warn('Voice SQL error:', result.error);
                } else {
                    const toolRoutes = ROUTES[functionName];
                    if (!toolRoutes) {
                        result = { error: `Unknown tool: ${functionName}` };
                    } else {
                        const urlBuilder = toolRoutes[args.query_type];
                        if (!urlBuilder) {
                            result = { error: `Unknown query_type "${args.query_type}" for ${functionName}` };
                        } else {
                            const url = urlBuilder(args);
                            const resp = await fetch(url);
                            result = await resp.json();
                        }
                    }
                }
            } catch (err) {
                result = { error: err.message };
            }

            const trimmed = truncateResult(result);
            if (functionName.startsWith('manage_')) {
                renderActionResult(result);
            } else {
                autoVisualize(result, functionName, args.query_type);
            }

            await responseDone; // wait for current response to finish
            if (dc && dc.readyState === 'open') {
                dc.send(JSON.stringify({
                    type: 'conversation.item.create',
                    item: {
                        type: 'function_call_output',
                        call_id: callId,
                        output: JSON.stringify(trimmed)
                    }
                }));
                dc.send(JSON.stringify({ type: 'response.create' }));
            }
        } finally {
            activeFunctionCalls--;
        }
    }

    // -----------------------------------------------------------------------
    // Truncate large results before sending back to the Realtime API.
    // The full data is rendered locally; only a summary goes to the model.
    // -----------------------------------------------------------------------
    const MAX_RESULT_CHARS = 4000;

    function truncateResult(data) {
        if (!data || typeof data !== 'object') return data;
        const raw = JSON.stringify(data);
        if (raw.length <= MAX_RESULT_CHARS) return data;

        // Trim arrays to first N items + add a count note
        const copy = { ...data };
        for (const key of Object.keys(copy)) {
            if (Array.isArray(copy[key]) && copy[key].length > 20) {
                const total = copy[key].length;
                copy[key] = copy[key].slice(0, 20);
                copy[key + '_total_count'] = total;
                copy[key + '_note'] = `Showing 20 of ${total}. Full data rendered on screen.`;
            }
        }
        // If rows[] (SQL result), trim too
        if (Array.isArray(copy.rows) && copy.rows.length > 20) {
            const total = copy.rows.length;
            copy.rows = copy.rows.slice(0, 20);
            copy.row_count = total;
            copy._note = `Showing 20 of ${total} rows.`;
        }
        // Final safety: hard truncate the string if still too big
        const trimmed = JSON.stringify(copy);
        if (trimmed.length > MAX_RESULT_CHARS) {
            return { _summary: trimmed.slice(0, MAX_RESULT_CHARS - 100), _truncated: true, _note: 'Result truncated. Key data rendered on screen.' };
        }
        return copy;
    }

    // -----------------------------------------------------------------------
    // Chart utilities & renderers
    // -----------------------------------------------------------------------
    function destroyActiveCharts() {
        activeCharts.forEach(c => { try { c.destroy(); } catch {} });
        activeCharts = [];
    }

    function createChartContainer(height) {
        const wrap = document.createElement('div');
        wrap.className = 'voice-chart-container';
        // Inner div is the actual Chart.js container — NO padding, position:relative
        const inner = document.createElement('div');
        inner.style.cssText = 'position:relative;width:100%;height:' + (height || 280) + 'px;';
        const canvas = document.createElement('canvas');
        canvas.style.display = 'block';
        inner.appendChild(canvas);
        wrap.appendChild(inner);
        return { wrap, canvas };
    }

    /** Create a Chart.js instance. Uses setTimeout to guarantee the
     *  browser has computed layout before Chart.js reads dimensions. */
    function initChart(canvas, config) {
        setTimeout(() => {
            if (!canvas.isConnected) return;
            try {
                const parent = canvas.parentElement;
                // If parent has no dimensions yet, set explicit fallbacks
                if (!parent || parent.clientWidth < 1) {
                    canvas.width = 350;
                    canvas.height = 280;
                }
                const ctx = canvas.getContext('2d');
                const chart = new Chart(ctx, config);
                activeCharts.push(chart);
            } catch (e) {
                console.error('Voice AI chart error:', e);
            }
        }, 60);
    }

    function darkChartOptions(overrides) {
        return Object.assign({
            responsive: true,
            maintainAspectRatio: false,
            animation: { duration: 600, easing: 'easeOutQuart' },
            plugins: {
                legend: {
                    display: false,
                    labels: { color: 'rgba(255,255,255,0.6)', font: { size: 12 } }
                },
                tooltip: {
                    backgroundColor: 'rgba(15,15,20,0.9)',
                    titleColor: 'rgba(255,255,255,0.8)',
                    bodyColor: 'rgba(255,255,255,0.7)',
                    borderColor: 'rgba(255,255,255,0.1)',
                    borderWidth: 1,
                    cornerRadius: 10,
                    padding: 10,
                }
            },
            scales: {
                x: {
                    ticks: { color: 'rgba(255,255,255,0.45)', font: { size: 11 } },
                    grid: { color: 'rgba(255,255,255,0.05)' },
                    border: { color: 'rgba(255,255,255,0.08)' },
                },
                y: {
                    ticks: { color: 'rgba(255,255,255,0.45)', font: { size: 11 } },
                    grid: { color: 'rgba(255,255,255,0.05)' },
                    border: { color: 'rgba(255,255,255,0.08)' },
                }
            }
        }, overrides || {});
    }

    function formatChartValue(val, fmt) {
        if (fmt === 'currency') return '$' + (typeof val === 'number' ? val.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 }) : val);
        if (fmt === 'percent') return (typeof val === 'number' ? val.toFixed(1) : val) + '%';
        return typeof val === 'number' ? val.toLocaleString('en-US') : val;
    }

    function tooltipCallback(fmt) {
        return {
            callbacks: {
                label: function(ctx) {
                    const lbl = ctx.dataset.label || '';
                    return lbl + ': ' + formatChartValue(ctx.parsed.y ?? ctx.parsed ?? ctx.raw, fmt);
                }
            }
        };
    }

    function tickCallback(fmt) {
        return function(value) { return formatChartValue(value, fmt); };
    }

    // --- Dispatch from create_visualization args ---
    function renderVisualization(args) {
        const { chart_type, title, labels, format } = args;
        // Normalize: AI may send datasets, data, or values in various shapes
        let datasets = args.datasets;
        if (!datasets && args.data) datasets = args.data;
        if (!datasets && args.values) datasets = [{ label: title || 'Value', values: args.values }];
        if (!Array.isArray(datasets)) datasets = [];
        // If AI sent flat numbers instead of {label, values} objects, wrap them
        if (datasets.length && typeof datasets[0] === 'number') {
            datasets = [{ label: title || 'Value', values: datasets }];
        }
        console.log('Voice viz:', { chart_type, title, labels, datasets, format });
        if (!labels || !datasets.length) {
            console.warn('Voice viz: missing labels or datasets', args);
            return;
        }
        if (title) {
            const titleEl = document.createElement('div');
            titleEl.className = 'voice-chart-title';
            titleEl.textContent = title;
            dataEl.appendChild(titleEl);
        }
        switch (chart_type) {
            case 'line':            renderLineChart(labels, datasets, format); break;
            case 'bar':             renderBarChart(labels, datasets, format); break;
            case 'horizontal_bar':  renderHorizontalBarChart(labels, datasets, format); break;
            case 'doughnut':        renderDoughnutChart(labels, datasets, format); break;
            default:                renderBarChart(labels, datasets, format);
        }
    }

    function renderLineChart(labels, datasets, fmt) {
        const { wrap, canvas } = createChartContainer(280);
        dataEl.appendChild(wrap);
        const opts = darkChartOptions();
        opts.plugins.tooltip = Object.assign(opts.plugins.tooltip || {}, tooltipCallback(fmt));
        if (fmt) opts.scales.y.ticks.callback = tickCallback(fmt);
        initChart(canvas, {
            type: 'line',
            data: {
                labels,
                datasets: datasets.map((ds, i) => ({
                    label: ds.label,
                    data: ds.values,
                    borderColor: CHART_COLORS[i % CHART_COLORS.length],
                    backgroundColor: CHART_COLORS_FILL[i % CHART_COLORS_FILL.length],
                    fill: true,
                    tension: 0.35,
                    pointRadius: 4,
                    pointHoverRadius: 6,
                    borderWidth: 2.5,
                }))
            },
            options: Object.assign(opts, {
                plugins: Object.assign(opts.plugins, {
                    legend: { display: datasets.length > 1, labels: { color: 'rgba(255,255,255,0.6)', font: { size: 12 }, usePointStyle: true, pointStyle: 'circle' } }
                })
            })
        });
    }

    function renderBarChart(labels, datasets, fmt) {
        const { wrap, canvas } = createChartContainer(280);
        dataEl.appendChild(wrap);
        const opts = darkChartOptions();
        opts.plugins.tooltip = Object.assign(opts.plugins.tooltip || {}, tooltipCallback(fmt));
        if (fmt) opts.scales.y.ticks.callback = tickCallback(fmt);
        initChart(canvas, {
            type: 'bar',
            data: {
                labels,
                datasets: datasets.map((ds, i) => ({
                    label: ds.label,
                    data: ds.values,
                    backgroundColor: CHART_COLORS[i % CHART_COLORS.length],
                    borderRadius: 6,
                    borderSkipped: false,
                    maxBarThickness: 48,
                }))
            },
            options: Object.assign(opts, {
                plugins: Object.assign(opts.plugins, {
                    legend: { display: datasets.length > 1, labels: { color: 'rgba(255,255,255,0.6)', font: { size: 12 } } }
                })
            })
        });
    }

    function renderHorizontalBarChart(labels, datasets, fmt) {
        const barH = 32;
        const height = Math.max(200, labels.length * barH + 60);
        const { wrap, canvas } = createChartContainer(height);
        dataEl.appendChild(wrap);
        const opts = darkChartOptions();
        opts.indexAxis = 'y';
        opts.plugins.tooltip = Object.assign(opts.plugins.tooltip || {}, tooltipCallback(fmt));
        if (fmt) opts.scales.x.ticks.callback = tickCallback(fmt);
        initChart(canvas, {
            type: 'bar',
            data: {
                labels,
                datasets: datasets.map((ds, i) => ({
                    label: ds.label,
                    data: ds.values,
                    backgroundColor: CHART_COLORS[i % CHART_COLORS.length],
                    borderRadius: 6,
                    borderSkipped: false,
                    maxBarThickness: 28,
                }))
            },
            options: opts
        });
    }

    function renderDoughnutChart(labels, datasets, fmt) {
        const { wrap, canvas } = createChartContainer(300);
        dataEl.appendChild(wrap);
        // Doughnut uses a flat array of values from the first dataset
        const values = datasets[0] ? datasets[0].values : [];
        const colors = labels.map((_, i) => CHART_COLORS[i % CHART_COLORS.length]);
        initChart(canvas, {
            type: 'doughnut',
            data: {
                labels,
                datasets: [{
                    data: values,
                    backgroundColor: colors,
                    borderColor: 'rgba(10,10,15,0.95)',
                    borderWidth: 3,
                    hoverOffset: 8,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: { duration: 600, easing: 'easeOutQuart' },
                cutout: '55%',
                plugins: {
                    legend: {
                        display: true,
                        position: 'right',
                        labels: {
                            color: 'rgba(255,255,255,0.6)',
                            font: { size: 12 },
                            padding: 14,
                            usePointStyle: true,
                            pointStyle: 'circle',
                        }
                    },
                    tooltip: {
                        backgroundColor: 'rgba(15,15,20,0.9)',
                        titleColor: 'rgba(255,255,255,0.8)',
                        bodyColor: 'rgba(255,255,255,0.7)',
                        borderColor: 'rgba(255,255,255,0.1)',
                        borderWidth: 1,
                        cornerRadius: 10,
                        padding: 10,
                        callbacks: {
                            label: function(ctx) {
                                const total = ctx.dataset.data.reduce((a, b) => a + b, 0);
                                const pct = total > 0 ? ((ctx.raw / total) * 100).toFixed(1) : 0;
                                const valStr = fmt ? formatChartValue(ctx.raw, fmt) : ctx.raw.toLocaleString('en-US');
                                return ` ${ctx.label}: ${valStr} (${pct}%)`;
                            }
                        }
                    }
                }
            }
        });
    }

    // -----------------------------------------------------------------------
    // Auto-visualization — intelligent chart for every quantitative response
    // -----------------------------------------------------------------------

    /** Infer value format from a column/key name */
    function detectFormat(colName) {
        if (!colName) return null;
        const c = colName.toLowerCase();
        if (/price|cost|spend|revenue|total|subtotal|amount|pay|wage|salary|profit|margin|value|balance|tip|discount|budget/.test(c)) return 'currency';
        if (/percent|pct|rate|ratio|growth|change|margin_pct|variance/.test(c)) return 'percent';
        return null;
    }

    /** Classify columns in a row-based dataset by sampling values */
    function classifyColumns(rows) {
        if (!rows || rows.length === 0) return {};
        const sample = rows.slice(0, Math.min(rows.length, 10));
        const cols = Object.keys(sample[0]);
        const result = {};
        for (const col of cols) {
            const lower = col.toLowerCase();
            // Date detection: name-based + value-based
            if (/date|month|week|period|day|year|quarter/.test(lower)) {
                result[col] = 'date';
                continue;
            }
            // Sample values
            const vals = sample.map(r => r[col]).filter(v => v != null);
            const allNumeric = vals.length > 0 && vals.every(v => typeof v === 'number' || (typeof v === 'string' && !isNaN(parseFloat(v)) && /^[\d,.$%-]+$/.test(v.trim())));
            // Check if string values look like dates
            const looksLikeDate = vals.length > 0 && vals.every(v => typeof v === 'string' && /^\d{4}[-/]\d{2}([-/]\d{2})?$/.test(v.trim()));
            if (looksLikeDate) {
                result[col] = 'date';
            } else if (allNumeric) {
                result[col] = 'numeric';
            } else {
                result[col] = 'categorical';
            }
        }
        return result;
    }

    /** Pick the best chart type given labels, datasets, and column analysis */
    function pickChartType(labels, datasets, analysis) {
        const n = labels.length;
        const dsCount = datasets.length;
        // Time-series → line
        if (analysis.hasDateAxis) return 'line';
        // Few categories + single metric → doughnut
        if (n >= 2 && n <= 8 && dsCount === 1) return 'doughnut';
        // Many items → horizontal bar for readability
        if (n > 10) return 'horizontal_bar';
        // Sorted descending data → horizontal bar (ranking feel)
        if (dsCount === 1 && n > 5) {
            const vals = datasets[0].values;
            let descending = true;
            for (let i = 1; i < vals.length; i++) {
                if (vals[i] > vals[i - 1]) { descending = false; break; }
            }
            if (descending) return 'horizontal_bar';
        }
        // Default
        return 'bar';
    }

    /** Generate a human-readable chart title */
    function generateTitle(toolName, queryType, columns) {
        const TITLES = {
            'query_sales:sales_overview': 'Sales Overview',
            'query_sales:sales_by_order_type': 'Sales by Order Type',
            'query_sales:time_comparison': 'Revenue Comparison',
            'query_sales:product_sales_details': 'Product Sales',
            'query_sales:sales_summary': 'Sales Summary',
            'query_suppliers:vendor_spend': 'Vendor Spend',
            'query_suppliers:category_spending': 'Spending by Category',
            'query_suppliers:supplier_performance': 'Supplier Performance',
            'query_invoices:invoice_activity': 'Invoice Activity',
            'query_analytics:usage_forecast': 'Usage Forecast',
            'query_analytics:price_trends': 'Price Trends',
            'query_analytics:menu_engineering': 'Menu Engineering',
            'query_analytics:recipe_cost_trajectory': 'Recipe Cost Trend',
            'query_analytics:seasonal_patterns': 'Seasonal Patterns',
            'query_analytics:inventory_value': 'Inventory Value',
            'query_inventory:summary': 'Inventory Summary',
            'query_payroll:summary': 'Payroll Summary',
        };
        const key = `${toolName}:${queryType}`;
        if (TITLES[key]) return TITLES[key];
        // Fallback: prettify the query type or first numeric column
        if (queryType) return prettifyHeader(queryType);
        if (columns && columns.length > 0) return prettifyHeader(columns[0]);
        return 'Overview';
    }

    /**
     * Core data extractor — normalize any API response shape into
     * { labels[], datasets[{label, values[]}], format, chartType }
     * Returns null if data is not chartable.
     */
    function extractChartData(result, toolName, queryType) {
        if (!result || result.error) return null;

        // --- Shape 1: {labels[], values[]} — vendor_spend, category_spending, sales_by_order_type ---
        if (Array.isArray(result.labels) && Array.isArray(result.values) && result.labels.length > 0) {
            if (!result.values.every(v => typeof v === 'number')) return null;
            const fmt = detectFormat(queryType) || 'currency';
            const ds = [{ label: generateTitle(toolName, queryType), values: result.values }];
            return {
                labels: result.labels,
                datasets: ds,
                format: fmt,
                chartType: pickChartType(result.labels, ds, { hasDateAxis: false }),
            };
        }

        // --- Shape 2: {labels[], datasets[{label, data[]}]} — invoice_activity, usage_forecast ---
        if (Array.isArray(result.labels) && Array.isArray(result.datasets) && result.datasets.length > 0) {
            const ds = result.datasets
                .filter(d => Array.isArray(d.data) && d.data.length > 0)
                .map(d => ({ label: d.label || 'Value', values: d.data }));
            if (ds.length === 0) return null;
            const hasDate = /date|month|week|period|day|year/i.test(result.labels[0] || '');
            const fmt = detectFormat(ds[0].label) || 'currency';
            return {
                labels: result.labels,
                datasets: ds,
                format: fmt,
                chartType: pickChartType(result.labels, ds, { hasDateAxis: hasDate || ds.length > 1 }),
            };
        }

        // --- Shape 3: sales_overview — {sales_by_date[], top_products[], sales_by_order_type[]} ---
        if (queryType === 'sales_overview') {
            // Prefer sales_by_date for line chart
            if (Array.isArray(result.sales_by_date) && result.sales_by_date.length >= 2) {
                const labels = result.sales_by_date.map(r => r.date || r.period || '');
                const ds = [{ label: 'Revenue', values: result.sales_by_date.map(r => r.revenue || r.total || 0) }];
                return { labels, datasets: ds, format: 'currency', chartType: 'line' };
            }
            // Fallback: sales_by_order_type
            if (Array.isArray(result.sales_by_order_type) && result.sales_by_order_type.length >= 2) {
                const labels = result.sales_by_order_type.map(r => r.order_type || r.type || '');
                const ds = [{ label: 'Sales', values: result.sales_by_order_type.map(r => r.revenue || r.total || r.count || 0) }];
                return { labels, datasets: ds, format: 'currency', chartType: 'doughnut' };
            }
            return null;
        }

        // --- Shape 4: time_comparison — {today:{}, this_week:{}, this_month:{}} ---
        if (queryType === 'time_comparison' || (result.today && result.this_week && result.this_month)) {
            const periods = [];
            const values = [];
            for (const [key, obj] of Object.entries(result)) {
                if (obj && typeof obj === 'object' && !Array.isArray(obj)) {
                    const val = obj.revenue || obj.total || obj.sales || obj.amount;
                    if (typeof val === 'number') {
                        periods.push(prettifyHeader(key));
                        values.push(val);
                    }
                }
            }
            if (periods.length >= 2) {
                return {
                    labels: periods,
                    datasets: [{ label: 'Revenue', values }],
                    format: 'currency',
                    chartType: 'bar',
                };
            }
            return null;
        }

        // --- Shape 5: {columns[], rows[{col:val}]} — run_sql_query ---
        if (Array.isArray(result.columns) && Array.isArray(result.rows) && result.rows.length >= 2 && result.columns.length >= 2) {
            const classified = classifyColumns(result.rows);
            // Find label column (date > categorical > first)
            let labelCol = result.columns.find(c => classified[c] === 'date');
            if (!labelCol) labelCol = result.columns.find(c => classified[c] === 'categorical');
            if (!labelCol) labelCol = result.columns[0];
            // Find numeric columns
            const numCols = result.columns.filter(c => c !== labelCol && classified[c] === 'numeric');
            if (numCols.length === 0) return null;
            const labels = result.rows.map(r => String(r[labelCol] || ''));
            const ds = numCols.map(col => ({
                label: prettifyHeader(col),
                values: result.rows.map(r => typeof r[col] === 'number' ? r[col] : parseFloat(r[col]) || 0),
            }));
            const hasDate = classified[labelCol] === 'date';
            const fmt = detectFormat(numCols[0]);
            return {
                labels,
                datasets: ds,
                format: fmt,
                chartType: pickChartType(labels, ds, { hasDateAxis: hasDate }),
            };
        }

        // --- Shape 6: {by_category[]} — inventory summary ---
        if (Array.isArray(result.by_category) && result.by_category.length >= 2) {
            const items = result.by_category;
            const labelKey = Object.keys(items[0]).find(k => /name|category|label|type/.test(k.toLowerCase())) || Object.keys(items[0])[0];
            const valKey = Object.keys(items[0]).find(k => {
                if (k === labelKey) return false;
                return items.every(r => typeof r[k] === 'number');
            });
            if (!labelKey || !valKey) return null;
            const labels = items.map(r => String(r[labelKey] || ''));
            const ds = [{ label: prettifyHeader(valKey), values: items.map(r => r[valKey]) }];
            const fmt = detectFormat(valKey);
            return {
                labels,
                datasets: ds,
                format: fmt,
                chartType: labels.length <= 8 ? 'doughnut' : 'horizontal_bar',
            };
        }

        // --- Shape 7: product_sales_details — {sales_by_date[], summary{}} ---
        if (Array.isArray(result.sales_by_date) && result.sales_by_date.length >= 2) {
            const labels = result.sales_by_date.map(r => r.date || r.period || '');
            const valKey = Object.keys(result.sales_by_date[0]).find(k => k !== 'date' && k !== 'period' && typeof result.sales_by_date[0][k] === 'number');
            if (!valKey) return null;
            const ds = [{ label: prettifyHeader(valKey), values: result.sales_by_date.map(r => r[valKey] || 0) }];
            return { labels, datasets: ds, format: detectFormat(valKey), chartType: 'line' };
        }

        // Non-chartable
        return null;
    }

    /**
     * Entry point — analyze result, render chart if appropriate.
     * Called automatically on every tool result.
     */
    function autoVisualize(result, toolName, queryType) {
        if (!result || result.error) return;
        const extracted = extractChartData(result, toolName, queryType);
        if (!extracted) return;
        const { labels, datasets, format, chartType } = extracted;
        if (!labels || labels.length === 0 || !datasets || datasets.length === 0) return;

        // Clear previous viz
        destroyActiveCharts();
        dataEl.innerHTML = '';
        newUserTurn = false; // chart is from THIS turn

        // Title
        const title = generateTitle(toolName, queryType, labels);
        const titleEl = document.createElement('div');
        titleEl.className = 'voice-chart-title';
        titleEl.textContent = title;
        dataEl.appendChild(titleEl);

        // Dispatch to existing renderers
        switch (chartType) {
            case 'line':           renderLineChart(labels, datasets, format); break;
            case 'doughnut':       renderDoughnutChart(labels, datasets, format); break;
            case 'horizontal_bar': renderHorizontalBarChart(labels, datasets, format); break;
            case 'bar':
            default:               renderBarChart(labels, datasets, format); break;
        }
    }

    // -----------------------------------------------------------------------
    // Data visualization renderer
    // -----------------------------------------------------------------------
    function renderData(data, toolName, queryType) {
        if (!data || data.error) return;
        destroyActiveCharts();
        dataEl.innerHTML = '';

        const charted = false; // autoVisualize handles charts now

        // Pattern 0: SQL query result — columns[] + rows[{...}] (from run_sql_query)
        // Skip table if auto-chart already rendered a chart for this data
        if (!charted && Array.isArray(data.columns) && Array.isArray(data.rows) && data.columns.length > 0 && data.rows.length > 0) {
            // Show row count badge
            const badge = document.createElement('div');
            badge.className = 'voice-data-badge';
            badge.textContent = `${data.row_count || data.rows.length} Results`;
            dataEl.appendChild(badge);

            const table = document.createElement('div');
            table.className = 'voice-data-table';
            const header = document.createElement('div');
            header.className = 'table-header';
            data.columns.forEach(c => {
                const cell = document.createElement('span');
                cell.className = 'table-cell';
                cell.textContent = prettifyHeader(c);
                header.appendChild(cell);
            });
            table.appendChild(header);
            const limit = Math.min(data.rows.length, 8);
            for (let i = 0; i < limit; i++) {
                const row = document.createElement('div');
                row.className = 'table-row';
                row.style.animationDelay = (i * 0.06) + 's';
                data.columns.forEach(col => {
                    const cell = document.createElement('span');
                    cell.className = 'table-cell';
                    const val = data.rows[i][col];
                    cell.textContent = typeof val === 'number' ? fmtNum(val) : (val ?? '');
                    row.appendChild(cell);
                });
                table.appendChild(row);
            }
            dataEl.appendChild(table);
            return;
        }

        // Pattern 1: labels[] + values[] → ranked list (vendor spend, category spending)
        // Skip if auto-chart already rendered a chart for this data
        if (!charted && Array.isArray(data.labels) && Array.isArray(data.values) && data.labels.length > 0) {
            const list = document.createElement('div');
            list.className = 'voice-data-list';
            const limit = Math.min(data.labels.length, 8);
            for (let i = 0; i < limit; i++) {
                const row = document.createElement('div');
                row.className = 'voice-data-row';
                row.style.animationDelay = (i * 0.08) + 's';
                row.innerHTML = `
                    <span class="rank">${i + 1}</span>
                    <span class="row-label">${esc(data.labels[i])}</span>
                    <span class="row-value">${fmtNum(data.values[i])}</span>
                `;
                list.appendChild(row);
            }
            dataEl.appendChild(list);
            return;
        }

        // Pattern 2: columns[] + rows[][] → table (supplier performance)
        if (!charted && Array.isArray(data.columns) && Array.isArray(data.rows) && data.rows.length > 0) {
            const table = document.createElement('div');
            table.className = 'voice-data-table';
            const header = document.createElement('div');
            header.className = 'table-header';
            data.columns.forEach(c => {
                const cell = document.createElement('span');
                cell.className = 'table-cell';
                cell.textContent = prettifyHeader(c);
                header.appendChild(cell);
            });
            table.appendChild(header);
            const limit = Math.min(data.rows.length, 6);
            for (let i = 0; i < limit; i++) {
                const row = document.createElement('div');
                row.className = 'table-row';
                row.style.animationDelay = (i * 0.08) + 's';
                data.rows[i].forEach(v => {
                    const cell = document.createElement('span');
                    cell.className = 'table-cell';
                    cell.textContent = typeof v === 'number' ? fmtNum(v) : (v ?? '');
                    row.appendChild(cell);
                });
                table.appendChild(row);
            }
            dataEl.appendChild(table);
            return;
        }

        // Pattern 3: Array of objects (orders, employees, schedules, attendance, invoices)
        const arrayKey = !charted && findArrayKey(data);
        if (arrayKey) {
            const arr = data[arrayKey];
            if (arr.length === 0) return;

            // Show count badge
            const badge = document.createElement('div');
            badge.className = 'voice-data-badge';
            badge.textContent = prettifyBadge(arrayKey, arr.length);
            dataEl.appendChild(badge);

            // Extract stats from array if numeric fields present
            const stats = extractArrayStats(arr, arrayKey);
            if (stats.length > 0) {
                renderStatCards(stats);
            }
            return;
        }

        // Pattern 4: Flat object with numeric/string values (summary, totals)
        if (!charted) {
            const stats = extractObjectStats(data);
            if (stats.length > 0) {
                renderStatCards(stats);
            }
        }
    }

    function renderStatCards(stats) {
        const grid = document.createElement('div');
        grid.className = 'voice-data-stats';
        stats.slice(0, 6).forEach(s => {
            const card = document.createElement('div');
            card.className = 'voice-data-stat';
            card.innerHTML = `<div class="value">${s.value}</div><div class="stat-label">${esc(s.label)}</div>`;
            grid.appendChild(card);
        });
        dataEl.appendChild(grid);
    }

    function findArrayKey(data) {
        const keys = ['orders', 'employees', 'schedules', 'attendance', 'pay_period', 'items', 'by_category'];
        for (const k of keys) {
            if (Array.isArray(data[k]) && data[k].length > 0) return k;
        }
        // Fallback: find first array property
        for (const k of Object.keys(data)) {
            if (Array.isArray(data[k]) && data[k].length > 0) return k;
        }
        return null;
    }

    function extractArrayStats(arr, key) {
        const stats = [];
        if (key === 'orders') {
            stats.push({ label: 'Orders', value: arr.length });
            const total = arr.reduce((s, o) => s + (parseFloat(o.total) || 0), 0);
            if (total > 0) stats.push({ label: 'Revenue', value: '$' + fmtNum(total) });
            const avg = total / arr.length;
            if (avg > 0) stats.push({ label: 'Avg Order', value: '$' + fmtNum(avg) });
        } else if (key === 'schedules') {
            stats.push({ label: 'Shifts', value: arr.length });
            const unique = new Set(arr.map(s => s.employee_name || s.employee_id)).size;
            stats.push({ label: 'Employees', value: unique });
        } else if (key === 'attendance') {
            stats.push({ label: 'Records', value: arr.length });
            const totalHrs = arr.reduce((s, a) => s + (parseFloat(a.total_hours) || 0), 0);
            if (totalHrs > 0) stats.push({ label: 'Total Hours', value: totalHrs.toFixed(1) });
        } else if (key === 'employees') {
            const byDept = {};
            arr.forEach(e => { const d = e.department || e.position || 'Staff'; byDept[d] = (byDept[d] || 0) + 1; });
            stats.push({ label: 'Team Size', value: arr.length });
            Object.entries(byDept).slice(0, 3).forEach(([d, c]) => stats.push({ label: d, value: c }));
        }
        return stats;
    }

    function extractObjectStats(data) {
        const stats = [];
        const labels = {
            total_value: 'Total Value', total_items: 'Items', unique_ingredients: 'Ingredients',
            total_spend: 'Total Spend', supplier_count: 'Suppliers', alert_count: 'Alerts',
            inventory_value: 'Inventory Value', total_hours: 'Total Hours',
            regular_hours: 'Regular Hours', ot_hours: 'Overtime Hours', gross_pay: 'Gross Pay',
            regular_wages: 'Regular Pay', ot_wages: 'Overtime Pay', tips: 'Tips',
        };
        // Check for nested totals object (payroll)
        const src = data.totals || data;
        for (const [k, v] of Object.entries(src)) {
            if (typeof v === 'number' && labels[k]) {
                const isDollar = k.includes('value') || k.includes('spend') || k.includes('pay') || k.includes('wages') || k.includes('tips');
                stats.push({ label: labels[k], value: isDollar ? '$' + fmtNum(v) : fmtNum(v) });
            }
        }
        // by_category summary
        if (Array.isArray(data.by_category) && data.by_category.length > 0) {
            stats.push({ label: 'Categories', value: data.by_category.length });
        }
        return stats;
    }

    function fmtNum(n) {
        if (typeof n !== 'number') return n;
        if (n >= 1000) return n.toLocaleString('en-US', { maximumFractionDigits: 0 });
        if (n % 1 !== 0) return n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        return n.toString();
    }

    function esc(s) {
        const d = document.createElement('div');
        d.textContent = s;
        return d.innerHTML;
    }

    function renderActionResult(result) {
        destroyActiveCharts();
        dataEl.innerHTML = '';
        newUserTurn = false;
        const card = document.createElement('div');
        card.className = 'voice-data-action ' + (result.success ? 'success' : 'error');
        card.innerHTML = `
            <div class="action-icon">${result.success ? '&#10003;' : '&#10007;'}</div>
            <div class="action-message">${esc(result.message || result.error || 'Unknown result')}</div>
        `;
        dataEl.appendChild(card);
    }

    // -----------------------------------------------------------------------
    // UI Helpers
    // -----------------------------------------------------------------------
    function setState(newState) {
        state = newState;
        btnMic.classList.toggle('active', state !== State.IDLE);
        statusDot.className = 'voice-ai-status-dot ' + state;
        if (!paused) {
            const labels = {
                idle: 'Ready',
                connecting: 'Connecting...',
                listening: 'Listening...',
                thinking: 'Thinking...',
                speaking: 'Speaking...',
            };
            statusText.textContent = labels[state] || '';
            waveform.classList.toggle('active', state === State.LISTENING || state === State.SPEAKING);
        }
    }

    function showError(msg) {
        aiResponse.textContent = msg;
        aiResponse.classList.add('error');
        setTimeout(() => aiResponse.classList.remove('error'), 4000);
    }

    // -----------------------------------------------------------------------
    // Boot
    // -----------------------------------------------------------------------
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
