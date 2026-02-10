/* =========================================================================
 *  storefront-checkout.js — Checkout flow, order submission, and tracking
 *  Handles the checkout form, payment, order submission, confirmation
 *  screen, and real-time order tracking.
 *  Vanilla JS, no frameworks, no build tools.
 *
 *  Works with the existing DOM from:
 *    - storefront/order.html (checkout form: #sfCheckout, confirmation: #sfConfirmation)
 *    - storefront/order_track.html (tracking: #sfTrackingContainer)
 *    - storefront/components/_checkout_form.html
 * ========================================================================= */

'use strict';

/* --------------------------------------------------------------------------
 *  Global State
 * ------------------------------------------------------------------------ */

const SFCheckout = {
    stripe: null,
    elements: null,
    cardElement: null,
    _submitting: false,
    _trackingPollTimer: null,
    _lookupTimer: null,
};


/* --------------------------------------------------------------------------
 *  Show Checkout
 * ------------------------------------------------------------------------ */

SFCheckout.show = function () {
    // Validate cart is not empty
    if (!SF.cart || SF.cart.length === 0) {
        SF.toast('Your cart is empty', 'error');
        return;
    }

    // Validate order type is selected
    if (!SF.orderType) {
        SF.toast('Please select an order type first', 'error');
        var picker = document.getElementById('sfOrderType');
        if (picker) picker.scrollIntoView({ behavior: 'smooth' });
        return;
    }

    // Close cart drawer if open
    if (SF.isCartOpen) SF.toggleCart();

    // Hide order page, show checkout
    var orderPage = document.getElementById('sfOrderPage');
    var checkout = document.getElementById('sfCheckout');

    if (orderPage) orderPage.style.display = 'none';
    if (checkout) checkout.style.display = '';

    // Hide bottom bar
    var bottomBar = document.getElementById('sfBottomBar');
    if (bottomBar) bottomBar.style.display = 'none';

    // Show/hide delivery address field
    var addressGroup = document.getElementById('sfAddressGroup');
    if (addressGroup) {
        addressGroup.style.display = SF.orderType === 'delivery' ? '' : 'none';
    }

    // Render checkout items and totals
    SFCheckout._renderCheckoutSummary();

    // Bind events
    SFCheckout._bindCheckoutEvents();

    // Scroll to top
    window.scrollTo({ top: 0, behavior: 'smooth' });
};


/* --------------------------------------------------------------------------
 *  Back to Menu
 * ------------------------------------------------------------------------ */

SFCheckout._backToMenu = function () {
    var orderPage = document.getElementById('sfOrderPage');
    var checkout = document.getElementById('sfCheckout');

    if (checkout) checkout.style.display = 'none';
    if (orderPage) orderPage.style.display = '';

    // Re-show bottom bar
    SF._updateBottomBar();

    window.scrollTo({ top: 0, behavior: 'smooth' });
};


/* --------------------------------------------------------------------------
 *  Render Checkout Summary
 * ------------------------------------------------------------------------ */

SFCheckout._renderCheckoutSummary = function () {
    var itemsContainer = document.getElementById('sfCheckoutItems');
    var totalsContainer = document.getElementById('sfCheckoutTotals');
    if (!itemsContainer) return;

    // Items
    var html = '';
    SF.cart.forEach(function (item) {
        var modsText = '';
        if (item.modifiers && item.modifiers.length > 0) {
            modsText = item.modifiers.map(function (m) { return m.name; }).join(', ');
        }

        html += '<div class="sf-checkout-item">';
        html += '<div class="sf-checkout-item__qty">' + item.quantity + 'x</div>';
        html += '<div class="sf-checkout-item__info">';
        html += '<span class="sf-checkout-item__name">' + SF.escapeHtml(item.name) + '</span>';
        if (item.sizeName) {
            html += '<span class="sf-checkout-item__detail">' + SF.escapeHtml(item.sizeName) + '</span>';
        }
        if (modsText) {
            html += '<span class="sf-checkout-item__detail">' + SF.escapeHtml(modsText) + '</span>';
        }
        if (item.specialInstructions) {
            html += '<span class="sf-checkout-item__detail sf-checkout-item__note">"' +
                SF.escapeHtml(item.specialInstructions) + '"</span>';
        }
        html += '</div>';
        html += '<div class="sf-checkout-item__price">' + SF.formatPrice(item.lineTotal) + '</div>';
        html += '</div>';
    });
    itemsContainer.innerHTML = html;

    // Totals
    if (totalsContainer) {
        var cfg = window.SF_CONFIG || {};
        var subtotal = SF.getCartTotal();
        var taxRate = cfg.taxRate || 0;
        var tax = taxRate > 0 ? Math.round(subtotal * taxRate) / 100 : 0;
        var deliveryFee = 0;
        if (SF.orderType === 'delivery' && cfg.deliveryFee) {
            deliveryFee = cfg.deliveryFee;
        }
        var total = Math.round((subtotal + tax + deliveryFee) * 100) / 100;

        var totalsHtml = '';
        totalsHtml += '<div class="sf-checkout__total-row">';
        totalsHtml += '<span>Subtotal</span><span>' + SF.formatPrice(subtotal) + '</span>';
        totalsHtml += '</div>';

        if (tax > 0) {
            totalsHtml += '<div class="sf-checkout__total-row">';
            totalsHtml += '<span>Tax (' + taxRate + '%)</span><span>' + SF.formatPrice(tax) + '</span>';
            totalsHtml += '</div>';
        }

        if (deliveryFee > 0) {
            totalsHtml += '<div class="sf-checkout__total-row">';
            totalsHtml += '<span>Delivery Fee</span><span>' + SF.formatPrice(deliveryFee) + '</span>';
            totalsHtml += '</div>';
        }

        totalsHtml += '<div class="sf-checkout__total-row sf-checkout__total-row--grand">';
        totalsHtml += '<span>Total</span><span>' + SF.formatPrice(total) + '</span>';
        totalsHtml += '</div>';

        totalsContainer.innerHTML = totalsHtml;
    }
};


/* --------------------------------------------------------------------------
 *  Bind Checkout Events
 * ------------------------------------------------------------------------ */

SFCheckout._bindCheckoutEvents = function () {
    // Phone number -> customer lookup with debounce
    var phoneInput = document.getElementById('sfCustPhone');
    if (phoneInput && !phoneInput._sfBound) {
        phoneInput._sfBound = true;
        phoneInput.addEventListener('input', function () {
            SFCheckout._formatPhoneInput(phoneInput);

            clearTimeout(SFCheckout._lookupTimer);
            SFCheckout._lookupTimer = setTimeout(function () {
                var digits = phoneInput.value.replace(/\D/g, '');
                if (digits.length >= 10) {
                    SFCheckout._doCustomerLookup(digits);
                }
            }, 500);
        });
    }

    // Place Order button (uses onclick in HTML, but also bind here for safety)
    var placeOrderBtn = document.getElementById('sfPlaceOrder');
    if (placeOrderBtn && !placeOrderBtn._sfBound) {
        placeOrderBtn._sfBound = true;
        placeOrderBtn.addEventListener('click', function (e) {
            e.preventDefault();
            SFCheckout.submit();
        });
    }

    // Payment radio cards
    var radios = document.querySelectorAll('#sfCheckout input[name="paymentMethod"]');
    radios.forEach(function (radio) {
        if (radio._sfBound) return;
        radio._sfBound = true;
        radio.addEventListener('change', function () {
            document.querySelectorAll('#sfCheckout .sf-radio-card').forEach(function (card) {
                card.classList.remove('sf-radio-card--active');
            });
            radio.closest('.sf-radio-card').classList.add('sf-radio-card--active');
        });
    });

    // Enter key on inputs submits
    var inputs = document.querySelectorAll('#sfCheckout .sf-input:not(.sf-textarea)');
    inputs.forEach(function (input) {
        if (input._sfBound) return;
        input._sfBound = true;
        input.addEventListener('keydown', function (e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                SFCheckout.submit();
            }
        });
    });
};


/* --------------------------------------------------------------------------
 *  Phone Formatting
 * ------------------------------------------------------------------------ */

SFCheckout._formatPhoneInput = function (input) {
    var digits = input.value.replace(/\D/g, '');
    if (digits.length === 0) {
        input.value = '';
        return;
    }

    var formatted = '';
    if (digits.length <= 3) {
        formatted = '(' + digits;
    } else if (digits.length <= 6) {
        formatted = '(' + digits.substring(0, 3) + ') ' + digits.substring(3);
    } else {
        formatted = '(' + digits.substring(0, 3) + ') ' + digits.substring(3, 6) +
            '-' + digits.substring(6, 10);
    }

    input.value = formatted;
};


/* --------------------------------------------------------------------------
 *  Customer Lookup
 * ------------------------------------------------------------------------ */

SFCheckout._doCustomerLookup = function (phone) {
    SF.lookupCustomer(phone, function (customer) {
        if (!customer) return;

        // Auto-fill fields that are empty
        var nameInput = document.getElementById('sfCustName');
        var emailInput = document.getElementById('sfCustEmail');
        var addressInput = document.getElementById('sfCustAddress');

        if (nameInput && !nameInput.value && customer.name) {
            nameInput.value = customer.name;
        }
        if (emailInput && !emailInput.value && customer.email) {
            emailInput.value = customer.email;
        }
        if (addressInput && !addressInput.value && customer.address) {
            addressInput.value = customer.address;
        }

        // Show welcome-back toast
        if (customer.name) {
            SF.toast('Welcome back, ' + customer.name + '!', 'success');
        }
    });
};


/* --------------------------------------------------------------------------
 *  Form Validation
 * ------------------------------------------------------------------------ */

SFCheckout._validate = function () {
    var errors = [];

    var nameInput = document.getElementById('sfCustName');
    var phoneInput = document.getElementById('sfCustPhone');
    var addressInput = document.getElementById('sfCustAddress');

    // Clear previous error states
    document.querySelectorAll('#sfCheckout .sf-input--error').forEach(function (el) {
        el.classList.remove('sf-input--error');
    });
    document.querySelectorAll('#sfCheckout .sf-form-error').forEach(function (el) {
        el.remove();
    });

    // Name
    if (!nameInput || !nameInput.value.trim()) {
        errors.push({ field: nameInput, message: 'Name is required' });
    }

    // Phone
    if (!phoneInput || !phoneInput.value.trim()) {
        errors.push({ field: phoneInput, message: 'Phone number is required' });
    } else {
        var digits = phoneInput.value.replace(/\D/g, '');
        if (digits.length < 10) {
            errors.push({ field: phoneInput, message: 'Please enter a valid 10-digit phone number' });
        }
    }

    // Address (delivery only)
    if (SF.orderType === 'delivery') {
        if (!addressInput || !addressInput.value.trim()) {
            errors.push({ field: addressInput, message: 'Delivery address is required' });
        }
    }

    // Show errors
    if (errors.length > 0) {
        errors.forEach(function (err) {
            if (err.field) {
                err.field.classList.add('sf-input--error');
                var errorEl = document.createElement('p');
                errorEl.className = 'sf-form-error';
                errorEl.textContent = err.message;
                err.field.parentNode.appendChild(errorEl);
            }
        });

        // Focus first error
        if (errors[0].field) {
            errors[0].field.scrollIntoView({ behavior: 'smooth', block: 'center' });
            errors[0].field.focus();
        }

        return false;
    }

    return true;
};


/* --------------------------------------------------------------------------
 *  Submit Order
 * ------------------------------------------------------------------------ */

SFCheckout.submit = function () {
    if (SFCheckout._submitting) return;

    // Validate form
    if (!SFCheckout._validate()) return;

    SFCheckout._submitting = true;
    var submitBtn = document.getElementById('sfPlaceOrder');
    if (!submitBtn) return;

    // Show loading state
    var originalHtml = submitBtn.innerHTML;
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span class="sf-spinner"></span> Placing Order...';

    // Gather form data
    var nameInput = document.getElementById('sfCustName');
    var phoneInput = document.getElementById('sfCustPhone');
    var emailInput = document.getElementById('sfCustEmail');
    var addressInput = document.getElementById('sfCustAddress');
    var notesInput = document.getElementById('sfOrderNotes');
    var paymentRadio = document.querySelector('#sfCheckout input[name="paymentMethod"]:checked');

    // Build cart items for API
    var items = SF.cart.map(function (cartItem) {
        return {
            menuItemId: cartItem.menuItemId,
            sizeId: cartItem.sizeId,
            quantity: cartItem.quantity,
            modifierIds: cartItem.modifierIds || [],
            specialInstructions: cartItem.specialInstructions || '',
            name: cartItem.name,
        };
    });

    var payload = {
        items: items,
        orderType: SF.orderType || 'pickup',
        customerName: nameInput ? nameInput.value.trim() : '',
        customerPhone: phoneInput ? phoneInput.value.replace(/\D/g, '') : '',
        customerEmail: emailInput ? emailInput.value.trim() : '',
        customerAddress: addressInput ? addressInput.value.trim() : '',
        notes: notesInput ? notesInput.value.trim() : '',
        payment: {
            method: paymentRadio ? paymentRadio.value : 'cash',
            details: {},
        },
    };

    SF._fetch('/api/storefront/order', {
        method: 'POST',
        body: JSON.stringify(payload),
    })
        .then(function (data) {
            SFCheckout._submitting = false;

            if (data && data.success) {
                // Clear cart
                SF.clearCart();

                // Show confirmation screen
                SFCheckout._showConfirmation(data.order);
            } else {
                var errMsg = (data && data.error) ? data.error : 'Something went wrong. Please try again.';
                SF.toast(errMsg, 'error');
                submitBtn.disabled = false;
                submitBtn.innerHTML = originalHtml;
            }
        })
        .catch(function (err) {
            SFCheckout._submitting = false;
            var errMsg = 'Something went wrong. Please try again.';
            if (err && err.data && err.data.error) {
                errMsg = err.data.error;
            }
            SF.toast(errMsg, 'error');
            submitBtn.disabled = false;
            submitBtn.innerHTML = originalHtml;
        });
};


/* --------------------------------------------------------------------------
 *  Confirmation Screen
 * ------------------------------------------------------------------------ */

SFCheckout._showConfirmation = function (order) {
    var cfg = window.SF_CONFIG || {};
    var baseUrl = SF._baseUrl || '';

    // Hide checkout, show confirmation
    var checkout = document.getElementById('sfCheckout');
    var confirmation = document.getElementById('sfConfirmation');

    if (checkout) checkout.style.display = 'none';
    if (confirmation) confirmation.style.display = '';

    // Fill in confirmation details
    var numberEl = document.getElementById('sfConfirmNumber');
    var estimateEl = document.getElementById('sfConfirmEstimate');
    var trackLink = document.getElementById('sfTrackLink');

    if (numberEl) {
        numberEl.textContent = 'Order #' + (order.orderNumber || '');
    }

    if (estimateEl) {
        var timeEst = '';
        if (SF.orderType === 'pickup') {
            timeEst = 'Estimated ready in ~' + (cfg.estimatedPickupMinutes || 20) + ' minutes';
        } else if (SF.orderType === 'delivery') {
            timeEst = 'Estimated delivery in ~' + (cfg.estimatedDeliveryMinutes || 45) + ' minutes';
        } else {
            timeEst = 'Your order is being prepared';
        }
        estimateEl.textContent = timeEst;
    }

    if (trackLink && order.trackingToken) {
        trackLink.href = baseUrl + '/order/track/' + order.trackingToken;
    }

    window.scrollTo({ top: 0, behavior: 'smooth' });
};


/* --------------------------------------------------------------------------
 *  Order Tracking Page
 * ------------------------------------------------------------------------ */

SFCheckout.initTracking = function (token) {
    if (!token) return;

    // Initial fetch
    SFCheckout._fetchOrderStatus(token);

    // Poll every 15 seconds
    SFCheckout._trackingPollTimer = setInterval(function () {
        SFCheckout._fetchOrderStatus(token);
    }, 15000);
};


SFCheckout._fetchOrderStatus = function (token) {
    SF._fetch('/api/storefront/order/' + encodeURIComponent(token) + '/status')
        .then(function (data) {
            if (data && data.success && data.order) {
                SFCheckout._renderTracking(data.order);

                // Stop polling on terminal statuses
                var status = data.order.status;
                if (status === 'closed' || status === 'completed' ||
                    status === 'ready' || status === 'cancelled') {
                    SFCheckout._stopTracking();
                }
            } else {
                SFCheckout._showTrackingError();
                SFCheckout._stopTracking();
            }
        })
        .catch(function () {
            // Don't stop polling on network errors — user may reconnect
            // But if we haven't rendered anything yet, show a transient message
            var content = document.getElementById('sfTrackContent');
            if (content && content.style.display === 'none') {
                // Still on initial load, keep the skeleton visible
            }
        });
};


SFCheckout._renderTracking = function (order) {
    // Hide loading skeleton, show content
    var loading = document.getElementById('sfTrackLoading');
    var content = document.getElementById('sfTrackContent');
    var errorEl = document.getElementById('sfTrackError');

    if (loading) loading.style.display = 'none';
    if (errorEl) errorEl.style.display = 'none';
    if (content) content.style.display = '';

    // Update progress steps
    SFCheckout._updateProgressSteps(order.status);

    // Update order details
    var orderNum = document.getElementById('sfTrackOrderNum');
    var orderType = document.getElementById('sfTrackOrderType');
    var orderTime = document.getElementById('sfTrackOrderTime');
    var trackItems = document.getElementById('sfTrackItems');
    var trackTotal = document.getElementById('sfTrackTotal');

    if (orderNum) {
        orderNum.textContent = 'Order #' + (order.order_number || '');
    }

    if (orderType) {
        var typeLabel = SFCheckout._orderTypeLabel(order.order_type);
        orderType.textContent = typeLabel;
    }

    if (orderTime) {
        if (order.estimated_ready_time && order.status !== 'ready' &&
            order.status !== 'closed' && order.status !== 'completed') {
            orderTime.textContent = 'Estimated ready: ' +
                SFCheckout._formatTime(order.estimated_ready_time);
        } else if (order.status === 'ready') {
            orderTime.textContent = 'Your order is ready!';
            orderTime.className = 'sf-track-details__time sf-track-details__time--ready';
        } else if (order.status === 'closed' || order.status === 'completed') {
            orderTime.textContent = 'Order completed';
        } else if (order.created_at) {
            orderTime.textContent = 'Placed ' + SFCheckout._formatTime(order.created_at);
        }
    }

    // Render items
    if (trackItems && order.items) {
        var html = '';
        order.items.forEach(function (item) {
            html += '<div class="sf-track-item">';
            html += '<span class="sf-track-item__qty">' + (item.quantity || 1) + 'x</span>';
            html += '<span class="sf-track-item__name">' +
                SF.escapeHtml(item.product_name || '') + '</span>';
            if (item.size_name) {
                html += '<span class="sf-track-item__size">(' +
                    SF.escapeHtml(item.size_name) + ')</span>';
            }
            html += '<span class="sf-track-item__price">' +
                SF.formatPrice(item.line_total || 0) + '</span>';
            html += '</div>';

            if (item.modifiers) {
                html += '<p class="sf-track-item__mods">' +
                    SF.escapeHtml(item.modifiers) + '</p>';
            }
            if (item.special_instructions) {
                html += '<p class="sf-track-item__note">"' +
                    SF.escapeHtml(item.special_instructions) + '"</p>';
            }
        });
        trackItems.innerHTML = html;
    }

    // Render totals
    if (trackTotal) {
        var totalsHtml = '';

        if (order.subtotal !== undefined && order.subtotal !== null) {
            totalsHtml += '<div class="sf-track-total__row">' +
                '<span>Subtotal</span><span>' + SF.formatPrice(order.subtotal) + '</span></div>';
        }
        if (order.tax_amount) {
            totalsHtml += '<div class="sf-track-total__row">' +
                '<span>Tax</span><span>' + SF.formatPrice(order.tax_amount) + '</span></div>';
        }
        if (order.delivery_fee) {
            totalsHtml += '<div class="sf-track-total__row">' +
                '<span>Delivery</span><span>' + SF.formatPrice(order.delivery_fee) + '</span></div>';
        }
        if (order.tip_amount) {
            totalsHtml += '<div class="sf-track-total__row">' +
                '<span>Tip</span><span>' + SF.formatPrice(order.tip_amount) + '</span></div>';
        }
        totalsHtml += '<div class="sf-track-total__row sf-track-total__row--grand">' +
            '<span>Total</span><span>' + SF.formatPrice(order.total || 0) + '</span></div>';

        trackTotal.innerHTML = totalsHtml;
    }
};


SFCheckout._updateProgressSteps = function (currentStatus) {
    // The tracking template has steps: confirmed, preparing, ready, closed
    var statusOrder = ['confirmed', 'preparing', 'ready', 'closed'];
    var currentIdx = statusOrder.indexOf(currentStatus);

    // Treat 'completed' same as 'closed'
    if (currentStatus === 'completed') currentIdx = statusOrder.indexOf('closed');

    var steps = document.querySelectorAll('#sfTrackProgress .sf-tracking__step');
    var lines = document.querySelectorAll('#sfTrackProgress .sf-tracking__line');

    steps.forEach(function (step, idx) {
        var stepStatus = step.getAttribute('data-step');
        var stepIdx = statusOrder.indexOf(stepStatus);

        step.classList.remove('sf-tracking__step--done', 'sf-tracking__step--active');

        if (stepIdx < currentIdx) {
            step.classList.add('sf-tracking__step--done');
        } else if (stepIdx === currentIdx) {
            step.classList.add('sf-tracking__step--active');
        }
    });

    lines.forEach(function (line, idx) {
        line.classList.remove('sf-tracking__line--done');
        if (idx < currentIdx) {
            line.classList.add('sf-tracking__line--done');
        }
    });
};


SFCheckout._showTrackingError = function () {
    var loading = document.getElementById('sfTrackLoading');
    var content = document.getElementById('sfTrackContent');
    var errorEl = document.getElementById('sfTrackError');

    if (loading) loading.style.display = 'none';
    if (content) content.style.display = 'none';
    if (errorEl) errorEl.style.display = '';
};


SFCheckout._stopTracking = function () {
    if (SFCheckout._trackingPollTimer) {
        clearInterval(SFCheckout._trackingPollTimer);
        SFCheckout._trackingPollTimer = null;
    }
};


/* --------------------------------------------------------------------------
 *  Helpers
 * ------------------------------------------------------------------------ */

SFCheckout._orderTypeLabel = function (type) {
    var labels = {
        'pickup': 'Pickup',
        'delivery': 'Delivery',
        'dine_in': 'Dine In',
        'dinein': 'Dine In',
    };
    return labels[type] || type || '';
};


SFCheckout._formatTime = function (timeStr) {
    if (!timeStr) return '';
    try {
        var d = new Date(timeStr);
        if (isNaN(d.getTime())) return timeStr;
        return d.toLocaleString(undefined, {
            month: 'short',
            day: 'numeric',
            hour: 'numeric',
            minute: '2-digit',
        });
    } catch (e) {
        return timeStr;
    }
};
