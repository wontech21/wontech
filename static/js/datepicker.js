/**
 * FIRINGup Custom Date/Time Picker
 * A modern, styled date and time picker to replace browser defaults
 */

(function() {
    'use strict';

    // Inject styles
    const styles = `
        .fp-picker-overlay {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.4);
            backdrop-filter: blur(4px);
            z-index: 10000;
            display: flex;
            align-items: center;
            justify-content: center;
            animation: fpFadeIn 0.2s ease;
        }

        @keyframes fpFadeIn {
            from { opacity: 0; }
            to { opacity: 1; }
        }

        @keyframes fpSlideUp {
            from { opacity: 0; transform: translateY(20px) scale(0.95); }
            to { opacity: 1; transform: translateY(0) scale(1); }
        }

        .fp-picker {
            background: white;
            border-radius: 20px;
            box-shadow: 0 24px 48px rgba(0, 0, 0, 0.2);
            overflow: hidden;
            min-width: 320px;
            animation: fpSlideUp 0.3s ease;
        }

        .fp-picker-header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            color: white;
            text-align: center;
        }

        .fp-picker-title {
            font-size: 14px;
            opacity: 0.9;
            margin-bottom: 4px;
        }

        .fp-picker-selected {
            font-size: 24px;
            font-weight: 700;
        }

        .fp-picker-nav {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 16px 20px;
            border-bottom: 1px solid #e9ecef;
        }

        .fp-picker-nav-btn {
            width: 36px;
            height: 36px;
            border: none;
            background: #f1f3f4;
            border-radius: 50%;
            cursor: pointer;
            font-size: 18px;
            color: #667eea;
            transition: all 0.2s;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        .fp-picker-nav-btn:hover {
            background: #667eea;
            color: white;
        }

        .fp-picker-month-year {
            font-weight: 700;
            font-size: 16px;
            color: #1f2937;
            cursor: pointer;
            padding: 8px 16px;
            border-radius: 8px;
            transition: background 0.2s;
        }

        .fp-picker-month-year:hover {
            background: #f1f3f4;
        }

        .fp-picker-weekdays {
            display: grid;
            grid-template-columns: repeat(7, 1fr);
            padding: 12px 16px 8px;
            gap: 4px;
        }

        .fp-picker-weekday {
            text-align: center;
            font-size: 12px;
            font-weight: 600;
            color: #9ca3af;
            text-transform: uppercase;
        }

        .fp-picker-days {
            display: grid;
            grid-template-columns: repeat(7, 1fr);
            padding: 8px 16px 16px;
            gap: 4px;
        }

        .fp-picker-day {
            aspect-ratio: 1;
            border: none;
            background: transparent;
            border-radius: 50%;
            cursor: pointer;
            font-size: 14px;
            font-weight: 500;
            color: #374151;
            transition: all 0.2s;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        .fp-picker-day:hover:not(.fp-picker-day-disabled):not(.fp-picker-day-empty) {
            background: #e0e7ff;
            color: #667eea;
        }

        .fp-picker-day-today {
            border: 2px solid #667eea;
        }

        .fp-picker-day-selected {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
            color: white !important;
        }

        .fp-picker-day-disabled {
            color: #d1d5db;
            cursor: not-allowed;
        }

        .fp-picker-day-empty {
            cursor: default;
        }

        .fp-picker-day-other-month {
            color: #9ca3af;
        }

        .fp-picker-actions {
            display: flex;
            justify-content: flex-end;
            gap: 12px;
            padding: 16px 20px;
            border-top: 1px solid #e9ecef;
            background: #f8f9fa;
        }

        .fp-picker-btn {
            padding: 10px 24px;
            border: none;
            border-radius: 10px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
        }

        .fp-picker-btn-cancel {
            background: white;
            color: #6b7280;
            border: 2px solid #e9ecef;
        }

        .fp-picker-btn-cancel:hover {
            background: #f1f3f4;
        }

        .fp-picker-btn-confirm {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }

        .fp-picker-btn-confirm:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
        }

        /* Time Picker Styles */
        .fp-time-picker-content {
            padding: 24px;
        }

        .fp-time-display {
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 8px;
            margin-bottom: 24px;
        }

        .fp-time-segment {
            display: flex;
            flex-direction: column;
            align-items: center;
        }

        .fp-time-scroll-btn {
            width: 40px;
            height: 32px;
            border: none;
            background: #f1f3f4;
            border-radius: 8px;
            cursor: pointer;
            font-size: 16px;
            color: #667eea;
            transition: all 0.2s;
        }

        .fp-time-scroll-btn:hover {
            background: #667eea;
            color: white;
        }

        .fp-time-value {
            font-size: 48px;
            font-weight: 700;
            color: #1f2937;
            padding: 8px 0;
            min-width: 80px;
            text-align: center;
        }

        .fp-time-separator {
            font-size: 48px;
            font-weight: 700;
            color: #667eea;
        }

        .fp-time-period {
            display: flex;
            flex-direction: column;
            gap: 8px;
            margin-left: 16px;
        }

        .fp-time-period-btn {
            padding: 12px 16px;
            border: 2px solid #e9ecef;
            background: white;
            border-radius: 10px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 600;
            color: #6b7280;
            transition: all 0.2s;
        }

        .fp-time-period-btn.active {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-color: transparent;
            color: white;
        }

        .fp-time-period-btn:hover:not(.active) {
            border-color: #667eea;
            color: #667eea;
        }

        .fp-time-presets {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 8px;
            margin-top: 16px;
            padding-top: 16px;
            border-top: 1px solid #e9ecef;
        }

        .fp-time-preset {
            padding: 10px;
            border: 2px solid #e9ecef;
            background: white;
            border-radius: 8px;
            cursor: pointer;
            font-size: 13px;
            font-weight: 600;
            color: #6b7280;
            transition: all 0.2s;
            text-align: center;
        }

        .fp-time-preset:hover {
            border-color: #667eea;
            color: #667eea;
            background: #f0f4ff;
        }

        /* Month/Year Selector */
        .fp-month-selector {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 8px;
            padding: 16px;
        }

        .fp-month-btn {
            padding: 12px;
            border: 2px solid #e9ecef;
            background: white;
            border-radius: 10px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 600;
            color: #374151;
            transition: all 0.2s;
        }

        .fp-month-btn:hover {
            border-color: #667eea;
            color: #667eea;
        }

        .fp-month-btn.current {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-color: transparent;
            color: white;
        }

        .fp-year-selector {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 16px;
            padding: 16px;
        }

        .fp-year-value {
            font-size: 24px;
            font-weight: 700;
            color: #1f2937;
            min-width: 100px;
            text-align: center;
        }

        /* Custom date input styling */
        input[type="date"].fp-styled,
        input[type="time"].fp-styled {
            cursor: pointer;
            background-image: none;
        }

        input[type="date"].fp-styled::-webkit-calendar-picker-indicator,
        input[type="time"].fp-styled::-webkit-calendar-picker-indicator {
            display: none;
        }
    `;

    // Inject styles into head
    const styleSheet = document.createElement('style');
    styleSheet.textContent = styles;
    document.head.appendChild(styleSheet);

    // Date Picker Class
    class FPDatePicker {
        constructor(input) {
            this.input = input;
            this.selectedDate = input.value ? new Date(input.value + 'T00:00:00') : new Date();
            this.viewDate = new Date(this.selectedDate);
            this.mode = 'days'; // 'days', 'months', 'years'

            this.init();
        }

        init() {
            this.input.classList.add('fp-styled');
            this.input.addEventListener('click', (e) => {
                e.preventDefault();
                this.open();
            });
            this.input.addEventListener('focus', (e) => {
                e.preventDefault();
                this.input.blur();
                this.open();
            });
        }

        open() {
            if (this.input.value) {
                this.selectedDate = new Date(this.input.value + 'T00:00:00');
                this.viewDate = new Date(this.selectedDate);
            }
            this.mode = 'days';
            this.render();
        }

        close() {
            const overlay = document.querySelector('.fp-picker-overlay');
            if (overlay) {
                overlay.remove();
            }
        }

        render() {
            this.close();

            const overlay = document.createElement('div');
            overlay.className = 'fp-picker-overlay';
            overlay.addEventListener('click', (e) => {
                if (e.target === overlay) this.close();
            });

            const picker = document.createElement('div');
            picker.className = 'fp-picker';

            if (this.mode === 'days') {
                picker.innerHTML = this.renderDays();
            } else if (this.mode === 'months') {
                picker.innerHTML = this.renderMonths();
            } else if (this.mode === 'years') {
                picker.innerHTML = this.renderYears();
            }

            overlay.appendChild(picker);
            document.body.appendChild(overlay);

            this.attachEvents(picker);
        }

        renderDays() {
            const months = ['January', 'February', 'March', 'April', 'May', 'June',
                           'July', 'August', 'September', 'October', 'November', 'December'];
            const weekdays = ['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'];

            const year = this.viewDate.getFullYear();
            const month = this.viewDate.getMonth();

            const firstDay = new Date(year, month, 1);
            const lastDay = new Date(year, month + 1, 0);
            const startPad = firstDay.getDay();

            const today = new Date();
            today.setHours(0, 0, 0, 0);

            let daysHtml = '';

            // Previous month days
            const prevMonthLast = new Date(year, month, 0).getDate();
            for (let i = startPad - 1; i >= 0; i--) {
                const day = prevMonthLast - i;
                daysHtml += `<button class="fp-picker-day fp-picker-day-other-month" data-date="${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}">${day}</button>`;
            }

            // Current month days
            for (let day = 1; day <= lastDay.getDate(); day++) {
                const date = new Date(year, month, day);
                const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
                const isToday = date.getTime() === today.getTime();
                const isSelected = this.selectedDate &&
                    date.getFullYear() === this.selectedDate.getFullYear() &&
                    date.getMonth() === this.selectedDate.getMonth() &&
                    date.getDate() === this.selectedDate.getDate();

                let classes = 'fp-picker-day';
                if (isToday) classes += ' fp-picker-day-today';
                if (isSelected) classes += ' fp-picker-day-selected';

                daysHtml += `<button class="${classes}" data-date="${dateStr}">${day}</button>`;
            }

            // Next month days
            const endPad = 42 - (startPad + lastDay.getDate());
            for (let day = 1; day <= endPad; day++) {
                daysHtml += `<button class="fp-picker-day fp-picker-day-other-month">${day}</button>`;
            }

            const selectedStr = this.selectedDate ?
                this.selectedDate.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' }) :
                'Select a date';

            return `
                <div class="fp-picker-header">
                    <div class="fp-picker-title">Selected Date</div>
                    <div class="fp-picker-selected">${selectedStr}</div>
                </div>
                <div class="fp-picker-nav">
                    <button class="fp-picker-nav-btn" data-action="prev-month">&#8249;</button>
                    <span class="fp-picker-month-year" data-action="show-months">${months[month]} ${year}</span>
                    <button class="fp-picker-nav-btn" data-action="next-month">&#8250;</button>
                </div>
                <div class="fp-picker-weekdays">
                    ${weekdays.map(d => `<div class="fp-picker-weekday">${d}</div>`).join('')}
                </div>
                <div class="fp-picker-days">
                    ${daysHtml}
                </div>
                <div class="fp-picker-actions">
                    <button class="fp-picker-btn fp-picker-btn-cancel" data-action="cancel">Cancel</button>
                    <button class="fp-picker-btn fp-picker-btn-confirm" data-action="today">Today</button>
                    <button class="fp-picker-btn fp-picker-btn-confirm" data-action="confirm">Confirm</button>
                </div>
            `;
        }

        renderMonths() {
            const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                           'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
            const currentMonth = this.viewDate.getMonth();

            return `
                <div class="fp-picker-header">
                    <div class="fp-picker-title">Select Month</div>
                    <div class="fp-picker-selected">${this.viewDate.getFullYear()}</div>
                </div>
                <div class="fp-year-selector">
                    <button class="fp-picker-nav-btn" data-action="prev-year">&#8249;</button>
                    <span class="fp-year-value" data-action="show-years">${this.viewDate.getFullYear()}</span>
                    <button class="fp-picker-nav-btn" data-action="next-year">&#8250;</button>
                </div>
                <div class="fp-month-selector">
                    ${months.map((m, i) => `
                        <button class="fp-month-btn ${i === currentMonth ? 'current' : ''}" data-month="${i}">${m}</button>
                    `).join('')}
                </div>
                <div class="fp-picker-actions">
                    <button class="fp-picker-btn fp-picker-btn-cancel" data-action="back-to-days">Back</button>
                </div>
            `;
        }

        renderYears() {
            const currentYear = this.viewDate.getFullYear();
            const startYear = currentYear - 6;

            let yearsHtml = '';
            for (let i = 0; i < 12; i++) {
                const year = startYear + i;
                yearsHtml += `<button class="fp-month-btn ${year === currentYear ? 'current' : ''}" data-year="${year}">${year}</button>`;
            }

            return `
                <div class="fp-picker-header">
                    <div class="fp-picker-title">Select Year</div>
                    <div class="fp-picker-selected">${startYear} - ${startYear + 11}</div>
                </div>
                <div class="fp-year-selector">
                    <button class="fp-picker-nav-btn" data-action="prev-years">&#8249;</button>
                    <span class="fp-year-value">${startYear} - ${startYear + 11}</span>
                    <button class="fp-picker-nav-btn" data-action="next-years">&#8250;</button>
                </div>
                <div class="fp-month-selector">
                    ${yearsHtml}
                </div>
                <div class="fp-picker-actions">
                    <button class="fp-picker-btn fp-picker-btn-cancel" data-action="back-to-months">Back</button>
                </div>
            `;
        }

        attachEvents(picker) {
            picker.addEventListener('click', (e) => {
                const action = e.target.dataset.action;
                const date = e.target.dataset.date;
                const month = e.target.dataset.month;
                const year = e.target.dataset.year;

                if (date && !e.target.classList.contains('fp-picker-day-disabled')) {
                    this.selectedDate = new Date(date + 'T00:00:00');
                    this.render();
                }

                if (month !== undefined) {
                    this.viewDate.setMonth(parseInt(month));
                    this.mode = 'days';
                    this.render();
                }

                if (year !== undefined) {
                    this.viewDate.setFullYear(parseInt(year));
                    this.mode = 'months';
                    this.render();
                }

                switch (action) {
                    case 'prev-month':
                        this.viewDate.setMonth(this.viewDate.getMonth() - 1);
                        this.render();
                        break;
                    case 'next-month':
                        this.viewDate.setMonth(this.viewDate.getMonth() + 1);
                        this.render();
                        break;
                    case 'prev-year':
                        this.viewDate.setFullYear(this.viewDate.getFullYear() - 1);
                        this.render();
                        break;
                    case 'next-year':
                        this.viewDate.setFullYear(this.viewDate.getFullYear() + 1);
                        this.render();
                        break;
                    case 'prev-years':
                        this.viewDate.setFullYear(this.viewDate.getFullYear() - 12);
                        this.render();
                        break;
                    case 'next-years':
                        this.viewDate.setFullYear(this.viewDate.getFullYear() + 12);
                        this.render();
                        break;
                    case 'show-months':
                        this.mode = 'months';
                        this.render();
                        break;
                    case 'show-years':
                        this.mode = 'years';
                        this.render();
                        break;
                    case 'back-to-days':
                        this.mode = 'days';
                        this.render();
                        break;
                    case 'back-to-months':
                        this.mode = 'months';
                        this.render();
                        break;
                    case 'today':
                        this.selectedDate = new Date();
                        this.selectedDate.setHours(0, 0, 0, 0);
                        this.viewDate = new Date(this.selectedDate);
                        this.confirm();
                        break;
                    case 'confirm':
                        this.confirm();
                        break;
                    case 'cancel':
                        this.close();
                        break;
                }
            });
        }

        confirm() {
            if (this.selectedDate) {
                const year = this.selectedDate.getFullYear();
                const month = String(this.selectedDate.getMonth() + 1).padStart(2, '0');
                const day = String(this.selectedDate.getDate()).padStart(2, '0');
                this.input.value = `${year}-${month}-${day}`;
                this.input.dispatchEvent(new Event('change', { bubbles: true }));
            }
            this.close();
        }
    }

    // Time Picker Class
    class FPTimePicker {
        constructor(input) {
            this.input = input;
            this.hours = 12;
            this.minutes = 0;
            this.period = 'AM';

            if (input.value) {
                this.parseTime(input.value);
            }

            this.init();
        }

        init() {
            this.input.classList.add('fp-styled');
            this.input.addEventListener('click', (e) => {
                e.preventDefault();
                this.open();
            });
            this.input.addEventListener('focus', (e) => {
                e.preventDefault();
                this.input.blur();
                this.open();
            });
        }

        parseTime(timeStr) {
            const [hours, minutes] = timeStr.split(':').map(Number);
            if (hours === 0) {
                this.hours = 12;
                this.period = 'AM';
            } else if (hours === 12) {
                this.hours = 12;
                this.period = 'PM';
            } else if (hours > 12) {
                this.hours = hours - 12;
                this.period = 'PM';
            } else {
                this.hours = hours;
                this.period = 'AM';
            }
            this.minutes = minutes || 0;
        }

        open() {
            if (this.input.value) {
                this.parseTime(this.input.value);
            }
            this.render();
        }

        close() {
            const overlay = document.querySelector('.fp-picker-overlay');
            if (overlay) {
                overlay.remove();
            }
        }

        render() {
            this.close();

            const overlay = document.createElement('div');
            overlay.className = 'fp-picker-overlay';
            overlay.addEventListener('click', (e) => {
                if (e.target === overlay) this.close();
            });

            const picker = document.createElement('div');
            picker.className = 'fp-picker';
            picker.innerHTML = this.renderContent();

            overlay.appendChild(picker);
            document.body.appendChild(overlay);

            this.attachEvents(picker);
        }

        renderContent() {
            const displayTime = `${this.hours}:${String(this.minutes).padStart(2, '0')} ${this.period}`;

            const presets = [
                { label: '9 AM', h: 9, m: 0, p: 'AM' },
                { label: '12 PM', h: 12, m: 0, p: 'PM' },
                { label: '3 PM', h: 3, m: 0, p: 'PM' },
                { label: '6 PM', h: 6, m: 0, p: 'PM' },
                { label: '7 PM', h: 7, m: 0, p: 'PM' },
                { label: '8 PM', h: 8, m: 0, p: 'PM' },
                { label: '9 PM', h: 9, m: 0, p: 'PM' },
                { label: '10 PM', h: 10, m: 0, p: 'PM' }
            ];

            return `
                <div class="fp-picker-header">
                    <div class="fp-picker-title">Select Time</div>
                    <div class="fp-picker-selected">${displayTime}</div>
                </div>
                <div class="fp-time-picker-content">
                    <div class="fp-time-display">
                        <div class="fp-time-segment">
                            <button class="fp-time-scroll-btn" data-action="hour-up">&#9650;</button>
                            <div class="fp-time-value" id="fp-hours">${this.hours}</div>
                            <button class="fp-time-scroll-btn" data-action="hour-down">&#9660;</button>
                        </div>
                        <div class="fp-time-separator">:</div>
                        <div class="fp-time-segment">
                            <button class="fp-time-scroll-btn" data-action="min-up">&#9650;</button>
                            <div class="fp-time-value" id="fp-minutes">${String(this.minutes).padStart(2, '0')}</div>
                            <button class="fp-time-scroll-btn" data-action="min-down">&#9660;</button>
                        </div>
                        <div class="fp-time-period">
                            <button class="fp-time-period-btn ${this.period === 'AM' ? 'active' : ''}" data-period="AM">AM</button>
                            <button class="fp-time-period-btn ${this.period === 'PM' ? 'active' : ''}" data-period="PM">PM</button>
                        </div>
                    </div>
                    <div class="fp-time-presets">
                        ${presets.map(p => `
                            <button class="fp-time-preset" data-preset-h="${p.h}" data-preset-m="${p.m}" data-preset-p="${p.p}">${p.label}</button>
                        `).join('')}
                    </div>
                </div>
                <div class="fp-picker-actions">
                    <button class="fp-picker-btn fp-picker-btn-cancel" data-action="cancel">Cancel</button>
                    <button class="fp-picker-btn fp-picker-btn-confirm" data-action="confirm">Confirm</button>
                </div>
            `;
        }

        attachEvents(picker) {
            picker.addEventListener('click', (e) => {
                const action = e.target.dataset.action;
                const period = e.target.dataset.period;
                const presetH = e.target.dataset.presetH;

                if (presetH !== undefined) {
                    this.hours = parseInt(e.target.dataset.presetH);
                    this.minutes = parseInt(e.target.dataset.presetM);
                    this.period = e.target.dataset.presetP;
                    this.updateDisplay(picker);
                }

                if (period) {
                    this.period = period;
                    picker.querySelectorAll('.fp-time-period-btn').forEach(btn => {
                        btn.classList.toggle('active', btn.dataset.period === period);
                    });
                    this.updateDisplay(picker);
                }

                switch (action) {
                    case 'hour-up':
                        this.hours = this.hours >= 12 ? 1 : this.hours + 1;
                        this.updateDisplay(picker);
                        break;
                    case 'hour-down':
                        this.hours = this.hours <= 1 ? 12 : this.hours - 1;
                        this.updateDisplay(picker);
                        break;
                    case 'min-up':
                        this.minutes = (this.minutes + 5) % 60;
                        this.updateDisplay(picker);
                        break;
                    case 'min-down':
                        this.minutes = this.minutes < 5 ? 55 : this.minutes - 5;
                        this.updateDisplay(picker);
                        break;
                    case 'confirm':
                        this.confirm();
                        break;
                    case 'cancel':
                        this.close();
                        break;
                }
            });
        }

        updateDisplay(picker) {
            picker.querySelector('#fp-hours').textContent = this.hours;
            picker.querySelector('#fp-minutes').textContent = String(this.minutes).padStart(2, '0');
            picker.querySelector('.fp-picker-selected').textContent =
                `${this.hours}:${String(this.minutes).padStart(2, '0')} ${this.period}`;
        }

        confirm() {
            let hours24 = this.hours;
            if (this.period === 'PM' && this.hours !== 12) {
                hours24 = this.hours + 12;
            } else if (this.period === 'AM' && this.hours === 12) {
                hours24 = 0;
            }

            this.input.value = `${String(hours24).padStart(2, '0')}:${String(this.minutes).padStart(2, '0')}`;
            this.input.dispatchEvent(new Event('change', { bubbles: true }));
            this.close();
        }
    }

    // Initialize all date/time inputs
    function initializePickers() {
        document.querySelectorAll('input[type="date"]:not(.fp-initialized)').forEach(input => {
            new FPDatePicker(input);
            input.classList.add('fp-initialized');
        });

        document.querySelectorAll('input[type="time"]:not(.fp-initialized)').forEach(input => {
            new FPTimePicker(input);
            input.classList.add('fp-initialized');
        });
    }

    // Initialize on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initializePickers);
    } else {
        initializePickers();
    }

    // Re-initialize when new elements are added (for dynamic content)
    const observer = new MutationObserver((mutations) => {
        mutations.forEach((mutation) => {
            mutation.addedNodes.forEach((node) => {
                if (node.nodeType === 1) {
                    if (node.matches && (node.matches('input[type="date"]') || node.matches('input[type="time"]'))) {
                        initializePickers();
                    }
                    if (node.querySelectorAll) {
                        const inputs = node.querySelectorAll('input[type="date"], input[type="time"]');
                        if (inputs.length > 0) {
                            initializePickers();
                        }
                    }
                }
            });
        });
    });

    observer.observe(document.body, { childList: true, subtree: true });

    // Expose for manual initialization
    window.FPDatePicker = FPDatePicker;
    window.FPTimePicker = FPTimePicker;
    window.initializeFPPickers = initializePickers;

})();
