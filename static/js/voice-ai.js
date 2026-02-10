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

    // DOM refs (set in init)
    let btnMic, panel, statusDot, statusText, transcript, aiResponse, btnClose, waveform, dataEl;

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
            items:                () => `/api/menu-admin/items`,
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
        waveform    = document.getElementById('voice-ai-waveform');
        dataEl      = document.getElementById('voice-ai-data');

        if (!btnMic) return; // Voice AI not rendered (employee role)

        btnMic.addEventListener('click', toggleVoice);
        btnClose.addEventListener('click', stopVoice);

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

            // 3. Get microphone and add track to peer connection
            localStream = await navigator.mediaDevices.getUserMedia({ audio: true });
            pc.addTrack(localStream.getTracks()[0], localStream);

            // 4. Create data channel for events
            dc = pc.createDataChannel('oai-events');
            dc.onopen = () => {
                // Configure session with VAD via data channel
                dc.send(JSON.stringify({
                    type: 'session.update',
                    session: {
                        turn_detection: {
                            type: 'server_vad',
                            threshold: 0.5,
                            prefix_padding_ms: 300,
                            silence_duration_ms: 700,
                        },
                    }
                }));
                setState(State.LISTENING);
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
        if (localStream) {
            localStream.getTracks().forEach(t => t.stop());
            localStream = null;
        }
        if (dc) { dc.close(); dc = null; }
        if (pc) { pc.close(); pc = null; }
        if (audioEl) audioEl.srcObject = null;
        setState(State.IDLE);
    }

    // -----------------------------------------------------------------------
    // Stop — tear down everything
    // -----------------------------------------------------------------------
    function stopVoice() {
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
        setState(State.IDLE);
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
            // User started speaking — clear text only, NOT data viz.
            // Data viz is cleared by renderData() when new data arrives.
            // This prevents echo/feedback from speaker triggering VAD
            // and wiping freshly rendered visuals.
            case 'input_audio_buffer.speech_started':
                transcript.textContent = '';
                aiResponse.textContent = '';
                break;

            // User's speech transcribed
            case 'conversation.item.input_audio_transcription.completed':
                if (msg.transcript) {
                    transcript.textContent = msg.transcript;
                }
                break;

            // Model started generating a response
            case 'response.created':
                setState(State.THINKING);
                break;

            // Audio response streaming — model is speaking
            case 'response.audio.delta':
                if (state !== State.SPEAKING) setState(State.SPEAKING);
                break;

            // Text delta from model (transcript of what it's saying)
            case 'response.audio_transcript.delta':
                if (msg.delta) {
                    aiResponse.textContent += msg.delta;
                }
                break;

            // Response fully done
            case 'response.done':
                if (state !== State.IDLE) setState(State.LISTENING);
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
        setState(State.THINKING);

        let args = {};
        try { args = JSON.parse(argsStr || '{}'); } catch { args = {}; }

        let result;
        try {
            if (functionName === 'run_sql_query') {
                // SQL query — POST to our backend
                const resp = await fetch('/api/voice/query', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ sql: args.sql }),
                });
                result = await resp.json();
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

        // Render data visualization
        renderData(result, functionName, args.query_type);

        // Truncate result to prevent oversized data channel messages.
        // Large arrays (e.g. 1000+ sales records) would choke the Realtime API.
        const trimmed = truncateResult(result);

        // Send function result back to OpenAI via data channel
        if (dc && dc.readyState === 'open') {
            dc.send(JSON.stringify({
                type: 'conversation.item.create',
                item: {
                    type: 'function_call_output',
                    call_id: callId,
                    output: JSON.stringify(trimmed)
                }
            }));
            // Trigger model to continue responding with the data
            dc.send(JSON.stringify({ type: 'response.create' }));
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
    // Data visualization renderer
    // -----------------------------------------------------------------------
    function renderData(data, toolName, queryType) {
        if (!data || data.error) return;
        dataEl.innerHTML = '';

        // Pattern 0: SQL query result — columns[] + rows[{...}] (from run_sql_query)
        if (Array.isArray(data.columns) && Array.isArray(data.rows) && data.columns.length > 0 && data.rows.length > 0) {
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
        if (Array.isArray(data.labels) && Array.isArray(data.values) && data.labels.length > 0) {
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
        if (Array.isArray(data.columns) && Array.isArray(data.rows) && data.rows.length > 0) {
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
        const arrayKey = findArrayKey(data);
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
        const stats = extractObjectStats(data);
        if (stats.length > 0) {
            renderStatCards(stats);
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

    // -----------------------------------------------------------------------
    // UI Helpers
    // -----------------------------------------------------------------------
    function setState(newState) {
        state = newState;
        btnMic.classList.toggle('active', state !== State.IDLE);
        statusDot.className = 'voice-ai-status-dot ' + state;
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
