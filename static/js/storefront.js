/* =========================================================================
 *  storefront.js — Main storefront JavaScript
 *  Menu display, item customization, cart management, order type selection.
 *  Vanilla JS, no frameworks, no build tools.
 *
 *  Works with the existing DOM from:
 *    - storefront/base.html
 *    - storefront/order.html (+ components: _order_type_picker, _cart_drawer,
 *      _item_modal, _checkout_form)
 *    - storefront/menu.html (+ components: _category_nav, _menu_item_card)
 *    - storefront/home.html
 * ========================================================================= */

'use strict';

/* --------------------------------------------------------------------------
 *  Global State
 * ------------------------------------------------------------------------ */

const SF = {
    org: null,           // Org info from /api/storefront/info
    menu: [],            // Menu tree (categories -> items -> sizes -> modifiers)
    cart: [],            // Cart items (persisted to sessionStorage)
    isCartOpen: false,
    orderType: null,     // 'pickup' | 'delivery' | 'dine_in'
    _baseUrl: '',        // Resolved base URL for API and links
    _observer: null,     // IntersectionObserver for category scroll spy
};


/* --------------------------------------------------------------------------
 *  Initialization
 * ------------------------------------------------------------------------ */

SF.init = function () {
    var cfg = window.SF_CONFIG || {};

    // Resolve base URL: /s/{slug} or '' (custom domain)
    SF._baseUrl = cfg.baseUrl || '';

    // Load cart from sessionStorage immediately so badge is correct
    SF.loadCart();
    SF._updateCartBadge();
    SF._updateBottomBar();

    // Init nav scroll behavior
    SF._initNavScroll();

    // Fetch org info (non-blocking)
    SF._fetch('/api/storefront/info')
        .then(function (data) {
            if (data && data.success) {
                SF.org = data.info;
            }
        })
        .catch(function () {
            // Non-critical — page can still function with SF_CONFIG data
        });

    // If menu.html provides server-rendered menu data, load it for the item modal
    if (window.SF_MENU_DATA) {
        SF.menu = window.SF_MENU_DATA;
        SF._initCategoryScrollSpy();
    }
};


/**
 * Called by order.html's inline script on DOMContentLoaded.
 * Initializes the full order page: loads menu via API, sets up cart, etc.
 */
SF.initOrderPage = function () {
    SF.init();

    // Default order type to pickup if enabled
    var cfg = window.SF_CONFIG || {};
    if (cfg.pickupEnabled) {
        SF.orderType = 'pickup';
    } else if (cfg.deliveryEnabled) {
        SF.orderType = 'delivery';
    } else if (cfg.dineinEnabled) {
        SF.orderType = 'dine_in';
    }

    // Show address field if delivery is default
    SF._toggleAddressField();

    // Load menu
    SF._loadMenu();
};


/* --------------------------------------------------------------------------
 *  Menu Loading
 * ------------------------------------------------------------------------ */

SF._loadMenu = function () {
    SF._fetch('/api/storefront/menu')
        .then(function (data) {
            if (data && data.success) {
                SF.menu = data.categories;
                SF._renderMenu(data.categories);
            } else {
                SF._showMenuError('Could not load the menu. Please try again.');
            }
        })
        .catch(function () {
            SF._showMenuError('Could not load the menu. Please check your connection.');
        });
};


SF._showMenuError = function (message) {
    var sections = document.getElementById('sfMenuSections');
    if (!sections) return;
    sections.innerHTML =
        '<div class="sf-error sf-text-center" style="padding: 3rem 1rem;">' +
        '<p style="margin-bottom: 1rem;">' + SF.escapeHtml(message) + '</p>' +
        '<button class="sf-btn sf-btn--primary" onclick="location.reload()">Try Again</button>' +
        '</div>';
};


/* --------------------------------------------------------------------------
 *  Menu Rendering (Order Page — dynamic via API)
 * ------------------------------------------------------------------------ */

SF._renderMenu = function (categories) {
    // Filter empty categories
    categories = categories.filter(function (c) {
        return c.items && c.items.length > 0;
    });

    // Render category pills
    SF._renderCategoryPills(categories);

    // Render menu sections
    var container = document.getElementById('sfMenuSections');
    if (!container) return;

    if (categories.length === 0) {
        container.innerHTML =
            '<div class="sf-empty sf-text-center" style="padding: 3rem 1rem;">' +
            '<p>No menu items available right now.</p>' +
            '</div>';
        return;
    }

    var html = '';
    categories.forEach(function (cat) {
        html += '<div class="sf-menu-section" id="category-' + cat.id +
            '" data-category-id="' + cat.id + '">';
        html += '<h2 class="sf-menu-section__title">' + SF.escapeHtml(cat.name) + '</h2>';
        if (cat.description) {
            html += '<p class="sf-menu-section__desc">' + SF.escapeHtml(cat.description) + '</p>';
        }
        html += '<div class="sf-grid-3">';

        cat.items.forEach(function (item) {
            html += SF._renderItemCard(item);
        });

        html += '</div></div>';
    });

    container.innerHTML = html;

    // Set up scroll spy
    SF._initCategoryScrollSpy();
};


SF._renderCategoryPills = function (categories) {
    var pillContainer = document.getElementById('sfCategoryPills');
    if (!pillContainer) return;

    var html = '';
    categories.forEach(function (cat, idx) {
        html += '<button class="sf-category-nav__pill' +
            (idx === 0 ? ' sf-category-nav__pill--active' : '') +
            '" data-category-id="' + cat.id +
            '" onclick="SF.scrollToCategory(' + cat.id + ')">' +
            SF.escapeHtml(cat.name) + '</button>';
    });

    pillContainer.innerHTML = html;
};


SF._renderItemCard = function (item) {
    var priceText = '';
    if (item.sizes && item.sizes.length > 1) {
        priceText = 'From $' + (item.starting_price || 0).toFixed(2);
    } else if (item.sizes && item.sizes.length === 1) {
        priceText = '$' + item.sizes[0].price.toFixed(2);
    } else {
        priceText = '$' + (item.starting_price || 0).toFixed(2);
    }

    var desc = item.description || '';
    var truncated = desc.length > 90 ? desc.substring(0, 90) + '...' : desc;

    var popularBadge = item.is_popular
        ? '<span class="sf-badge sf-badge--popular">Popular</span>'
        : '';

    var dietaryBadges = '';
    if (item.dietary_tags && item.dietary_tags.length > 0) {
        item.dietary_tags.forEach(function (tag) {
            dietaryBadges += '<span class="sf-badge sf-badge--' +
                tag.toLowerCase() + '">' + SF.escapeHtml(tag) + '</span>';
        });
    }

    return '<div class="sf-card" data-item-id="' + item.id +
        '" onclick="SF.openItemModal(' + item.id + ')">' +
        popularBadge +
        '<div class="sf-card__body">' +
        '<h3 class="sf-card__name">' + SF.escapeHtml(item.name) + '</h3>' +
        (truncated ? '<p class="sf-card__desc">' + SF.escapeHtml(truncated) + '</p>' : '') +
        '<div class="sf-card__footer">' +
        '<span class="sf-card__price">' + priceText + '</span>' +
        (dietaryBadges ? '<div class="sf-card__badges">' + dietaryBadges + '</div>' : '') +
        '</div></div></div>';
};


/* --------------------------------------------------------------------------
 *  Category Scroll Spy + Navigation
 * ------------------------------------------------------------------------ */

SF._initCategoryScrollSpy = function () {
    if (SF._observer) {
        SF._observer.disconnect();
    }

    var sections = document.querySelectorAll('.sf-menu-section[data-category-id]');
    if (sections.length === 0) return;

    SF._observer = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
            if (entry.isIntersecting) {
                var catId = entry.target.getAttribute('data-category-id');
                SF._setActivePill(catId);
            }
        });
    }, {
        rootMargin: '-100px 0px -60% 0px',
        threshold: 0,
    });

    sections.forEach(function (section) {
        SF._observer.observe(section);
    });
};


SF._setActivePill = function (catId) {
    var pills = document.querySelectorAll('.sf-category-nav__pill');
    pills.forEach(function (pill) {
        pill.classList.toggle(
            'sf-category-nav__pill--active',
            pill.getAttribute('data-category-id') === String(catId)
        );
    });

    // Scroll the active pill into view horizontally
    var active = document.querySelector('.sf-category-nav__pill--active');
    if (active) {
        var scrollParent = active.parentElement;
        if (scrollParent) {
            var pillLeft = active.offsetLeft;
            var pillWidth = active.offsetWidth;
            var parentWidth = scrollParent.offsetWidth;
            scrollParent.scrollTo({
                left: pillLeft - (parentWidth / 2) + (pillWidth / 2),
                behavior: 'smooth',
            });
        }
    }
};


SF.scrollToCategory = function (catId) {
    var section = document.getElementById('category-' + catId);
    if (!section) return;

    var navHeight = 60;
    var catNav = document.getElementById('sfCategoryNav');
    if (catNav) navHeight += catNav.offsetHeight;

    var top = section.getBoundingClientRect().top + window.pageYOffset - navHeight - 16;
    window.scrollTo({ top: top, behavior: 'smooth' });

    SF._setActivePill(catId);
};


/* --------------------------------------------------------------------------
 *  Order Type Selection
 * ------------------------------------------------------------------------ */

SF.setOrderType = function (type) {
    SF.orderType = type;

    // Update button active states
    var cards = document.querySelectorAll('.sf-order-type__card');
    cards.forEach(function (card) {
        card.classList.toggle(
            'sf-order-type__card--active',
            card.getAttribute('data-type') === type
        );
    });

    // Show/hide delivery address in checkout form
    SF._toggleAddressField();

    // Re-render cart drawer totals (delivery fee may change)
    SF._renderCartContents();
};


SF._toggleAddressField = function () {
    var group = document.getElementById('sfAddressGroup');
    if (group) {
        group.style.display = SF.orderType === 'delivery' ? '' : 'none';
    }
};


/* --------------------------------------------------------------------------
 *  Item Modal
 * ------------------------------------------------------------------------ */

SF.openItemModal = function (itemId) {
    var item = SF._findItem(itemId);
    if (!item) return;

    var overlay = document.getElementById('sfModalOverlay');
    var modal = document.getElementById('sfItemModal');
    var body = document.getElementById('sfModalBody');
    if (!overlay || !modal || !body) return;

    // Build modal state
    var state = {
        item: item,
        selectedSizeIdx: 0,
        selectedModifiers: {},   // groupId -> [modifierId, ...]
        quantity: 1,
        specialInstructions: '',
    };

    // Pre-select first modifier for required_single groups
    if (item.modifier_groups) {
        item.modifier_groups.forEach(function (group) {
            if (group.selection_type === 'required_single' && group.modifiers && group.modifiers.length > 0) {
                state.selectedModifiers[group.id] = [group.modifiers[0].id];
            }
        });
    }

    // Render modal body
    body.innerHTML = SF._buildModalBody(item, state);

    // Store state on the modal element for event handlers
    modal._state = state;

    // Show panel (no overlay, no scroll lock — user can keep browsing)
    modal.classList.add('sf-modal--visible');

    // Bind events
    SF._bindModalEvents(modal, state);

    // Escape to close
    SF._modalEscHandler = function (e) {
        if (e.key === 'Escape') SF.closeItemModal();
    };
    document.addEventListener('keydown', SF._modalEscHandler);
};


SF.closeItemModal = function () {
    var modal = document.getElementById('sfItemModal');
    if (modal) {
        modal.classList.remove('sf-modal--visible');
        // Reset position so it reappears at default corner next time
        modal.style.top = '';
        modal.style.left = '';
        modal.style.bottom = '';
        modal.style.right = '';
    }

    if (SF._modalEscHandler) {
        document.removeEventListener('keydown', SF._modalEscHandler);
        SF._modalEscHandler = null;
    }
};


/* --------------------------------------------------------------------------
 *  Draggable Panel
 * ------------------------------------------------------------------------ */

SF._initDrag = function () {
    var handle = document.getElementById('sfModalDrag');
    var modal = document.getElementById('sfItemModal');
    if (!handle || !modal) return;

    var startX, startY, startLeft, startTop;

    function onStart(clientX, clientY) {
        var rect = modal.getBoundingClientRect();
        // Switch from bottom/right positioning to top/left for drag
        modal.style.top = rect.top + 'px';
        modal.style.left = rect.left + 'px';
        modal.style.bottom = 'auto';
        modal.style.right = 'auto';

        startX = clientX;
        startY = clientY;
        startLeft = rect.left;
        startTop = rect.top;
        modal.classList.add('sf-modal--dragging');
    }

    function onMove(clientX, clientY) {
        if (!modal.classList.contains('sf-modal--dragging')) return;
        var dx = clientX - startX;
        var dy = clientY - startY;
        var newLeft = Math.max(0, Math.min(window.innerWidth - 60, startLeft + dx));
        var newTop = Math.max(0, Math.min(window.innerHeight - 60, startTop + dy));
        modal.style.left = newLeft + 'px';
        modal.style.top = newTop + 'px';
    }

    function onEnd() {
        modal.classList.remove('sf-modal--dragging');
    }

    // Mouse events
    handle.addEventListener('mousedown', function (e) {
        e.preventDefault();
        onStart(e.clientX, e.clientY);
        function mouseMove(e) { onMove(e.clientX, e.clientY); }
        function mouseUp() {
            onEnd();
            document.removeEventListener('mousemove', mouseMove);
            document.removeEventListener('mouseup', mouseUp);
        }
        document.addEventListener('mousemove', mouseMove);
        document.addEventListener('mouseup', mouseUp);
    });

    // Touch events
    handle.addEventListener('touchstart', function (e) {
        var t = e.touches[0];
        onStart(t.clientX, t.clientY);
    }, { passive: true });
    document.addEventListener('touchmove', function (e) {
        if (!modal.classList.contains('sf-modal--dragging')) return;
        var t = e.touches[0];
        onMove(t.clientX, t.clientY);
    }, { passive: true });
    document.addEventListener('touchend', function () {
        if (modal.classList.contains('sf-modal--dragging')) onEnd();
    });
};

// Initialize drag once DOM is ready
document.addEventListener('DOMContentLoaded', SF._initDrag);


SF._buildModalBody = function (item, state) {
    var size = item.sizes[state.selectedSizeIdx] || (item.sizes.length ? item.sizes[0] : null);
    var sizeId = size ? size.id : null;
    var html = '';

    // Item name and description
    html += '<h2 class="sf-modal__title">' + SF.escapeHtml(item.name) + '</h2>';
    if (item.description) {
        html += '<p class="sf-modal__desc">' + SF.escapeHtml(item.description) + '</p>';
    }

    // Dietary badges
    if (item.dietary_tags && item.dietary_tags.length > 0) {
        html += '<div class="sf-modal__badges">';
        item.dietary_tags.forEach(function (tag) {
            html += '<span class="sf-badge sf-badge--' + tag.toLowerCase() + '">' +
                SF.escapeHtml(tag) + '</span>';
        });
        html += '</div>';
    }

    // Size selector
    if (item.sizes.length > 1) {
        html += '<div class="sf-modal__section">';
        html += '<label class="sf-modal__label">Size <span class="sf-required">*</span></label>';
        html += '<div class="sf-size-selector" id="sfSizeSelector">';
        item.sizes.forEach(function (s, idx) {
            var active = idx === state.selectedSizeIdx ? ' sf-size-pill--active' : '';
            html += '<button class="sf-size-pill' + active +
                '" data-size-idx="' + idx + '" data-size-id="' + s.id + '" type="button">' +
                '<span class="sf-size-pill__name">' + SF.escapeHtml(s.size_name) + '</span>' +
                '<span class="sf-size-pill__price">' + SF.formatPrice(s.price) + '</span>' +
                '</button>';
        });
        html += '</div></div>';
    } else if (item.sizes.length === 1) {
        html += '<p class="sf-modal__price">' + SF.formatPrice(item.sizes[0].price) + '</p>';
    }

    // Modifier groups
    if (item.modifier_groups && item.modifier_groups.length > 0) {
        item.modifier_groups.forEach(function (group) {
            html += SF._buildModifierGroup(group, sizeId, state);
        });
    }

    // Special instructions
    html += '<div class="sf-modal__section">';
    html += '<label class="sf-modal__label" for="sfModalInstructions">Special Instructions</label>';
    html += '<textarea class="sf-input sf-textarea" id="sfModalInstructions" ' +
        'placeholder="Any allergies or special requests..." maxlength="500" rows="2"></textarea>';
    html += '</div>';

    // Quantity + Add to Cart
    var total = SF._calcItemTotal(item, state);
    html += '<div class="sf-modal__actions">';
    html += '<div class="sf-qty" id="sfModalQty">';
    html += '<button class="sf-qty__btn" id="sfQtyMinus" type="button" aria-label="Decrease">&minus;</button>';
    html += '<span class="sf-qty__value" id="sfQtyValue">1</span>';
    html += '<button class="sf-qty__btn" id="sfQtyPlus" type="button" aria-label="Increase">+</button>';
    html += '</div>';

    var addLabel = (window.SF_MENU_MODE === 'view')
        ? 'View Only'
        : 'Add to Cart &mdash; ' + SF.formatPrice(total);
    var addDisabled = (window.SF_MENU_MODE === 'view') ? ' disabled' : '';
    html += '<button class="sf-btn sf-btn--primary sf-btn--lg sf-modal__add" id="sfAddToCart"' +
        addDisabled + '>' + addLabel + '</button>';
    html += '</div>';

    return html;
};


SF._buildModifierGroup = function (group, sizeId, state) {
    var isRequired = group.selection_type === 'required_single';
    var isSingle = group.selection_type === 'single' || isRequired;

    var html = '<div class="sf-modal__section sf-modifier-group" data-group-id="' + group.id + '">';
    html += '<label class="sf-modal__label">';
    html += SF.escapeHtml(group.name);
    if (isRequired) {
        html += ' <span class="sf-required">*Required</span>';
    } else if (isSingle) {
        html += ' <span class="sf-optional">(Optional)</span>';
    } else {
        html += ' <span class="sf-optional">(Choose any)</span>';
    }
    if (group.max_selections && !isSingle) {
        html += ' <span class="sf-optional">(Max ' + group.max_selections + ')</span>';
    }
    html += '</label>';

    html += '<div class="sf-modifier-list">';
    if (!group.modifiers || group.modifiers.length === 0) {
        html += '<p class="sf-text-muted">No options available</p>';
    } else {
        group.modifiers.forEach(function (mod, midx) {
            var modPrice = SF._getModifierPrice(mod, sizeId);
            var priceLabel = modPrice > 0 ? '+' + SF.formatPrice(modPrice) : '';
            var inputType = isSingle ? 'radio' : 'checkbox';
            var inputName = 'mod_group_' + group.id;
            var inputId = 'mod_' + group.id + '_' + mod.id;

            var checked = '';
            if (isRequired && midx === 0) checked = ' checked';

            html += '<label class="sf-modifier" for="' + inputId + '">';
            html += '<input type="' + inputType + '" id="' + inputId + '" name="' + inputName +
                '" value="' + mod.id + '" class="sf-modifier__input" ' +
                'data-group-id="' + group.id + '" data-mod-id="' + mod.id +
                '" data-single="' + (isSingle ? '1' : '0') + '"' + checked + '>';
            html += '<span class="sf-modifier__check"></span>';
            html += '<span class="sf-modifier__name">' + SF.escapeHtml(mod.name) + '</span>';
            html += '<span class="sf-modifier__price" data-mod-id="' + mod.id + '">' +
                priceLabel + '</span>';
            html += '</label>';
        });
    }

    html += '</div></div>';
    return html;
};


SF._bindModalEvents = function (modal, state) {
    var item = state.item;
    var body = document.getElementById('sfModalBody');
    if (!body) return;

    // Size pills
    var sizeSelector = body.querySelector('#sfSizeSelector');
    if (sizeSelector) {
        sizeSelector.addEventListener('click', function (e) {
            var pill = e.target.closest('.sf-size-pill');
            if (!pill) return;

            var idx = parseInt(pill.getAttribute('data-size-idx'), 10);
            state.selectedSizeIdx = idx;

            // Update active state
            sizeSelector.querySelectorAll('.sf-size-pill').forEach(function (p) {
                p.classList.remove('sf-size-pill--active');
            });
            pill.classList.add('sf-size-pill--active');

            // Update modifier prices for new size
            SF._updateModifierPrices(body, item, state);
            SF._updateModalTotal(body, item, state);
        });
    }

    // Modifier inputs
    body.querySelectorAll('.sf-modifier__input').forEach(function (input) {
        input.addEventListener('change', function () {
            var groupId = parseInt(input.getAttribute('data-group-id'), 10);
            var modId = parseInt(input.getAttribute('data-mod-id'), 10);
            var isSingle = input.getAttribute('data-single') === '1';

            if (isSingle) {
                state.selectedModifiers[groupId] = input.checked ? [modId] : [];
            } else {
                if (!state.selectedModifiers[groupId]) {
                    state.selectedModifiers[groupId] = [];
                }
                var arr = state.selectedModifiers[groupId];
                if (input.checked) {
                    // Check max selections
                    var group = SF._findModifierGroup(item, groupId);
                    if (group && group.max_selections && arr.length >= group.max_selections) {
                        input.checked = false;
                        SF.toast('Maximum ' + group.max_selections + ' selections allowed', 'error');
                        return;
                    }
                    if (arr.indexOf(modId) === -1) arr.push(modId);
                } else {
                    var idx = arr.indexOf(modId);
                    if (idx !== -1) arr.splice(idx, 1);
                }
            }

            SF._updateModalTotal(body, item, state);
        });
    });

    // Quantity controls
    var qtyMinus = body.querySelector('#sfQtyMinus');
    var qtyPlus = body.querySelector('#sfQtyPlus');
    var qtyValue = body.querySelector('#sfQtyValue');

    if (qtyMinus) {
        qtyMinus.addEventListener('click', function () {
            if (state.quantity > 1) {
                state.quantity--;
                qtyValue.textContent = state.quantity;
                SF._updateModalTotal(body, item, state);
            }
        });
    }
    if (qtyPlus) {
        qtyPlus.addEventListener('click', function () {
            if (state.quantity < 99) {
                state.quantity++;
                qtyValue.textContent = state.quantity;
                SF._updateModalTotal(body, item, state);
            }
        });
    }

    // Add to Cart
    var addBtn = body.querySelector('#sfAddToCart');
    if (addBtn && !addBtn.disabled) {
        addBtn.addEventListener('click', function () {
            // Validate required modifier groups
            if (item.modifier_groups) {
                for (var g = 0; g < item.modifier_groups.length; g++) {
                    var grp = item.modifier_groups[g];
                    if (grp.selection_type === 'required_single') {
                        var sel = state.selectedModifiers[grp.id] || [];
                        if (sel.length === 0) {
                            SF.toast('Please select a ' + grp.name, 'error');
                            return;
                        }
                    }
                }
            }

            // Read special instructions
            var instrEl = body.querySelector('#sfModalInstructions');
            state.specialInstructions = instrEl ? instrEl.value.trim() : '';

            SF._addItemToCart(item, state);
            SF.closeItemModal();
            SF.toast(item.name + ' added to cart', 'success');
        });
    }
};


SF._updateModifierPrices = function (container, item, state) {
    var size = item.sizes[state.selectedSizeIdx] || (item.sizes.length ? item.sizes[0] : null);
    var sizeId = size ? size.id : null;

    container.querySelectorAll('.sf-modifier__price').forEach(function (priceEl) {
        var modId = parseInt(priceEl.getAttribute('data-mod-id'), 10);
        var mod = SF._findModifier(item, modId);
        if (!mod) return;

        var price = SF._getModifierPrice(mod, sizeId);
        priceEl.textContent = price > 0 ? '+' + SF.formatPrice(price) : '';
    });
};


SF._updateModalTotal = function (container, item, state) {
    if (window.SF_MENU_MODE === 'view') return;

    var total = SF._calcItemTotal(item, state);
    var btn = container.querySelector('#sfAddToCart');
    if (btn) {
        btn.innerHTML = 'Add to Cart &mdash; ' + SF.formatPrice(total);
    }
};


SF._calcItemTotal = function (item, state) {
    var size = item.sizes[state.selectedSizeIdx] || (item.sizes.length ? item.sizes[0] : null);
    var sizeId = size ? size.id : null;
    var basePrice = size ? size.price : 0;

    var modTotal = 0;
    var groups = Object.keys(state.selectedModifiers);
    for (var i = 0; i < groups.length; i++) {
        var modIds = state.selectedModifiers[groups[i]];
        if (!modIds) continue;
        for (var j = 0; j < modIds.length; j++) {
            var mod = SF._findModifier(item, modIds[j]);
            if (mod) modTotal += SF._getModifierPrice(mod, sizeId);
        }
    }

    return (basePrice + modTotal) * state.quantity;
};


SF._getModifierPrice = function (mod, sizeId) {
    if (sizeId && mod.size_prices && mod.size_prices[sizeId] !== undefined) {
        return mod.size_prices[sizeId];
    }
    return mod.default_price || 0;
};


/* --------------------------------------------------------------------------
 *  Item / Modifier Lookups
 * ------------------------------------------------------------------------ */

SF._findItem = function (itemId) {
    for (var c = 0; c < SF.menu.length; c++) {
        var cat = SF.menu[c];
        if (!cat.items) continue;
        for (var i = 0; i < cat.items.length; i++) {
            if (cat.items[i].id === itemId) return cat.items[i];
        }
    }
    return null;
};


SF._findModifierGroup = function (item, groupId) {
    if (!item.modifier_groups) return null;
    for (var i = 0; i < item.modifier_groups.length; i++) {
        if (item.modifier_groups[i].id === groupId) return item.modifier_groups[i];
    }
    return null;
};


SF._findModifier = function (item, modId) {
    if (!item.modifier_groups) return null;
    for (var g = 0; g < item.modifier_groups.length; g++) {
        var group = item.modifier_groups[g];
        if (!group.modifiers) continue;
        for (var m = 0; m < group.modifiers.length; m++) {
            if (group.modifiers[m].id === modId) return group.modifiers[m];
        }
    }
    return null;
};


/* --------------------------------------------------------------------------
 *  Cart Management
 * ------------------------------------------------------------------------ */

SF._addItemToCart = function (item, state) {
    var size = item.sizes[state.selectedSizeIdx] || (item.sizes.length ? item.sizes[0] : null);
    var sizeId = size ? size.id : null;

    // Build selected modifiers list
    var modifiers = [];
    var modifierIds = [];
    var groups = Object.keys(state.selectedModifiers);
    for (var i = 0; i < groups.length; i++) {
        var ids = state.selectedModifiers[groups[i]] || [];
        for (var j = 0; j < ids.length; j++) {
            var mod = SF._findModifier(item, ids[j]);
            if (mod) {
                var price = SF._getModifierPrice(mod, sizeId);
                modifiers.push({
                    id: mod.id,
                    name: mod.name,
                    price: price,
                    groupId: parseInt(groups[i], 10),
                });
                modifierIds.push(mod.id);
            }
        }
    }

    var unitPrice = (size ? size.price : 0) +
        modifiers.reduce(function (sum, m) { return sum + m.price; }, 0);

    var cartItem = {
        _cartId: Date.now() + '_' + Math.random().toString(36).substr(2, 5),
        menuItemId: item.id,
        name: item.name,
        sizeId: sizeId,
        sizeName: size ? size.size_name : '',
        quantity: state.quantity,
        unitPrice: unitPrice,
        lineTotal: Math.round(unitPrice * state.quantity * 100) / 100,
        modifiers: modifiers,
        modifierIds: modifierIds,
        specialInstructions: state.specialInstructions || '',
    };

    SF.cart.push(cartItem);
    SF.saveCart();
    SF._updateCartBadge();
    SF._updateBottomBar();
    SF._renderCartContents();
};


SF.removeFromCart = function (index) {
    if (index < 0 || index >= SF.cart.length) return;
    SF.cart.splice(index, 1);
    SF.saveCart();
    SF._updateCartBadge();
    SF._updateBottomBar();
    SF._renderCartContents();
};


SF.updateCartQty = function (index, newQty) {
    if (index < 0 || index >= SF.cart.length) return;
    newQty = parseInt(newQty, 10);

    if (newQty <= 0) {
        SF.removeFromCart(index);
        return;
    }
    if (newQty > 99) newQty = 99;

    SF.cart[index].quantity = newQty;
    SF.cart[index].lineTotal = Math.round(SF.cart[index].unitPrice * newQty * 100) / 100;
    SF.saveCart();
    SF._updateCartBadge();
    SF._updateBottomBar();
    SF._renderCartContents();
};


SF.getCartTotal = function () {
    return SF.cart.reduce(function (sum, item) {
        return Math.round((sum + item.lineTotal) * 100) / 100;
    }, 0);
};


SF.getCartCount = function () {
    return SF.cart.reduce(function (sum, item) { return sum + item.quantity; }, 0);
};


SF.saveCart = function () {
    var key = 'sf_cart_' + (window.SF_CONFIG ? window.SF_CONFIG.slug : 'default');
    try {
        sessionStorage.setItem(key, JSON.stringify(SF.cart));
    } catch (e) {
        // Storage quota exceeded — degrade gracefully
    }
};


SF.loadCart = function () {
    var key = 'sf_cart_' + (window.SF_CONFIG ? window.SF_CONFIG.slug : 'default');
    try {
        var data = sessionStorage.getItem(key);
        if (data) {
            SF.cart = JSON.parse(data);
            if (!Array.isArray(SF.cart)) SF.cart = [];
        }
    } catch (e) {
        SF.cart = [];
    }
};


SF.clearCart = function () {
    SF.cart = [];
    SF.saveCart();
    SF._updateCartBadge();
    SF._updateBottomBar();
    SF._renderCartContents();
};


/* --------------------------------------------------------------------------
 *  Cart Badge + Bottom Bar
 * ------------------------------------------------------------------------ */

SF._updateCartBadge = function () {
    var count = SF.getCartCount();
    var badge = document.getElementById('sfCartBadge');
    if (badge) {
        badge.textContent = count;
        badge.style.display = count > 0 ? '' : 'none';
    }
};


SF._updateBottomBar = function () {
    var bar = document.getElementById('sfBottomBar');
    if (!bar) return;

    var count = SF.getCartCount();
    var total = SF.getCartTotal();

    if (count === 0) {
        bar.style.display = 'none';
        return;
    }

    bar.style.display = '';
    var countEl = document.getElementById('sfBottomCount');
    var totalEl = document.getElementById('sfBottomTotal');

    if (countEl) countEl.textContent = count + ' item' + (count !== 1 ? 's' : '');
    if (totalEl) totalEl.textContent = SF.formatPrice(total);
};


/* --------------------------------------------------------------------------
 *  Cart Drawer
 * ------------------------------------------------------------------------ */

SF.toggleCart = function () {
    SF.isCartOpen = !SF.isCartOpen;

    var cart = document.getElementById('sfCart');
    var overlay = document.getElementById('sfCartOverlay');

    if (!cart) return;

    if (SF.isCartOpen) {
        SF._renderCartContents();
        cart.classList.add('sf-cart--open');
        if (overlay) overlay.classList.add('sf-cart-overlay--visible');
        document.body.classList.add('sf-no-scroll');
    } else {
        cart.classList.remove('sf-cart--open');
        if (overlay) overlay.classList.remove('sf-cart-overlay--visible');
        document.body.classList.remove('sf-no-scroll');
    }
};


SF._renderCartContents = function () {
    var cartBody = document.getElementById('sfCartBody');
    var cartFooter = document.getElementById('sfCartFooter');
    var cartEmpty = document.getElementById('sfCartEmpty');
    if (!cartBody) return;

    if (SF.cart.length === 0) {
        // Show empty state, hide footer
        if (cartEmpty) cartEmpty.style.display = '';
        if (cartFooter) cartFooter.style.display = 'none';

        // Remove any rendered items
        var existingItems = cartBody.querySelectorAll('.sf-cart-item');
        existingItems.forEach(function (el) { el.remove(); });
        return;
    }

    // Hide empty state, show footer
    if (cartEmpty) cartEmpty.style.display = 'none';
    if (cartFooter) cartFooter.style.display = '';

    // Build items HTML
    var html = '';
    SF.cart.forEach(function (item, index) {
        var modsText = '';
        if (item.modifiers && item.modifiers.length > 0) {
            modsText = item.modifiers.map(function (m) { return m.name; }).join(', ');
        }

        html += '<div class="sf-cart-item">';
        html += '<div class="sf-cart-item__info">';
        html += '<span class="sf-cart-item__name">' + SF.escapeHtml(item.name) + '</span>';
        if (item.sizeName) {
            html += '<span class="sf-cart-item__detail">' + SF.escapeHtml(item.sizeName) + '</span>';
        }
        if (modsText) {
            html += '<span class="sf-cart-item__detail">' + SF.escapeHtml(modsText) + '</span>';
        }
        if (item.specialInstructions) {
            html += '<span class="sf-cart-item__detail sf-cart-item__note">"' +
                SF.escapeHtml(item.specialInstructions) + '"</span>';
        }
        html += '</div>';

        html += '<div class="sf-cart-item__right">';
        html += '<div class="sf-qty sf-qty--sm">';
        html += '<button class="sf-qty__btn" type="button" onclick="SF.updateCartQty(' +
            index + ',' + (item.quantity - 1) + ')" aria-label="Decrease">&minus;</button>';
        html += '<span class="sf-qty__value">' + item.quantity + '</span>';
        html += '<button class="sf-qty__btn" type="button" onclick="SF.updateCartQty(' +
            index + ',' + (item.quantity + 1) + ')" aria-label="Increase">+</button>';
        html += '</div>';
        html += '<span class="sf-cart-item__price">' + SF.formatPrice(item.lineTotal) + '</span>';
        html += '<button class="sf-cart-item__remove" type="button" onclick="SF.removeFromCart(' +
            index + ')" aria-label="Remove">&times;</button>';
        html += '</div>';

        html += '</div>';
    });

    // Replace only the items portion (preserve the empty state element)
    var existingItems = cartBody.querySelectorAll('.sf-cart-item');
    existingItems.forEach(function (el) { el.remove(); });
    cartBody.insertAdjacentHTML('afterbegin', html);

    // Update totals
    SF._updateCartTotals();
};


SF._updateCartTotals = function () {
    var cfg = window.SF_CONFIG || {};
    var subtotal = SF.getCartTotal();
    var taxRate = cfg.taxRate || 0;
    var tax = taxRate > 0 ? Math.round(subtotal * taxRate) / 100 : 0;
    var deliveryFee = 0;

    if (SF.orderType === 'delivery' && cfg.deliveryFee) {
        deliveryFee = cfg.deliveryFee;
    }

    var total = Math.round((subtotal + tax + deliveryFee) * 100) / 100;

    // Cart drawer totals
    var subtotalEl = document.getElementById('sfCartSubtotal');
    var taxEl = document.getElementById('sfCartTax');
    var deliveryRow = document.getElementById('sfCartDeliveryRow');
    var deliveryFeeEl = document.getElementById('sfCartDeliveryFee');
    var totalEl = document.getElementById('sfCartTotal');

    if (subtotalEl) subtotalEl.textContent = SF.formatPrice(subtotal);
    if (taxEl) taxEl.textContent = SF.formatPrice(tax);
    if (deliveryRow) deliveryRow.style.display = deliveryFee > 0 ? '' : 'none';
    if (deliveryFeeEl) deliveryFeeEl.textContent = SF.formatPrice(deliveryFee);
    if (totalEl) totalEl.textContent = SF.formatPrice(total);
};


/* --------------------------------------------------------------------------
 *  Mobile Nav Toggle
 * ------------------------------------------------------------------------ */

SF.toggleMobileNav = function () {
    var links = document.getElementById('sfNavLinks');
    var hamburger = document.getElementById('sfHamburger');
    if (!links) return;

    var isOpen = links.classList.toggle('sf-nav__links--open');
    if (hamburger) hamburger.classList.toggle('sf-nav__hamburger--active', isOpen);
};


/* --------------------------------------------------------------------------
 *  Nav Scroll Behavior
 * ------------------------------------------------------------------------ */

SF._initNavScroll = function () {
    var nav = document.getElementById('sfNav');
    if (!nav) return;

    var ticking = false;

    window.addEventListener('scroll', function () {
        if (!ticking) {
            requestAnimationFrame(function () {
                var scrollY = window.pageYOffset || document.documentElement.scrollTop;
                nav.classList.toggle('sf-nav--scrolled', scrollY > 50);
                ticking = false;
            });
            ticking = true;
        }
    }, { passive: true });
};


/* --------------------------------------------------------------------------
 *  Customer Lookup
 * ------------------------------------------------------------------------ */

SF.lookupCustomer = function (phone, callback) {
    if (!phone || phone.length < 7) {
        callback(null);
        return;
    }

    SF._fetch('/api/storefront/customer/lookup', {
        method: 'POST',
        body: JSON.stringify({ phone: phone }),
    })
        .then(function (data) {
            if (data && data.success && data.customer) {
                callback(data.customer);
            } else {
                callback(null);
            }
        })
        .catch(function () {
            callback(null);
        });
};


/* --------------------------------------------------------------------------
 *  Toast Notifications
 * ------------------------------------------------------------------------ */

SF.toast = function (message, type) {
    type = type || 'info';

    var container = document.getElementById('sfToastContainer');
    if (!container) {
        container = document.createElement('div');
        container.className = 'sf-toast-container';
        container.id = 'sfToastContainer';
        document.body.appendChild(container);
    }

    var toast = document.createElement('div');
    toast.className = 'sf-toast sf-toast--' + type;

    var iconSvg = '';
    if (type === 'success') {
        iconSvg = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
            'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
            '<path d="M22 11.08V12a10 10 0 11-5.93-9.14"/>' +
            '<polyline points="22 4 12 14.01 9 11.01"/></svg>';
    } else if (type === 'error') {
        iconSvg = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
            'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
            '<circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/>' +
            '<line x1="12" y1="16" x2="12.01" y2="16"/></svg>';
    } else {
        iconSvg = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
            'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
            '<circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/>' +
            '<line x1="12" y1="8" x2="12.01" y2="8"/></svg>';
    }

    toast.innerHTML =
        '<span class="sf-toast__icon">' + iconSvg + '</span>' +
        '<span class="sf-toast__message">' + SF.escapeHtml(message) + '</span>' +
        '<button class="sf-toast__close" type="button" aria-label="Dismiss">&times;</button>';

    container.appendChild(toast);

    // Animate in
    requestAnimationFrame(function () {
        toast.classList.add('sf-toast--visible');
    });

    // Auto-dismiss
    var timer = setTimeout(function () {
        SF._dismissToast(toast);
    }, 3000);

    // Manual dismiss
    toast.querySelector('.sf-toast__close').addEventListener('click', function () {
        clearTimeout(timer);
        SF._dismissToast(toast);
    });
};


SF._dismissToast = function (toast) {
    toast.classList.remove('sf-toast--visible');
    toast.classList.add('sf-toast--leaving');
    setTimeout(function () {
        if (toast.parentNode) toast.parentNode.removeChild(toast);
    }, 300);
};


/* --------------------------------------------------------------------------
 *  Utility Functions
 * ------------------------------------------------------------------------ */

SF.formatPrice = function (amount) {
    if (typeof amount !== 'number' || isNaN(amount)) return '$0.00';
    return '$' + amount.toFixed(2);
};


SF.slugify = function (text) {
    return String(text)
        .toLowerCase()
        .trim()
        .replace(/[^\w\s-]/g, '')
        .replace(/[\s_]+/g, '-')
        .replace(/^-+|-+$/g, '');
};


SF.debounce = function (fn, delay) {
    var timer = null;
    return function () {
        var context = this;
        var args = arguments;
        clearTimeout(timer);
        timer = setTimeout(function () {
            fn.apply(context, args);
        }, delay);
    };
};


SF.escapeHtml = function (str) {
    if (str === null || str === undefined) return '';
    var s = String(str);
    return s
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
};


/* --------------------------------------------------------------------------
 *  API Fetch Helper
 * ------------------------------------------------------------------------ */

SF._fetch = function (path, options) {
    var url = SF._baseUrl + path;
    var defaults = {
        method: 'GET',
        headers: {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        },
    };

    options = options || {};
    var config = {
        method: options.method || defaults.method,
        headers: Object.assign({}, defaults.headers, options.headers || {}),
    };
    if (options.body) {
        config.body = options.body;
    }

    return fetch(url, config)
        .then(function (response) {
            if (!response.ok) {
                return response.json().then(function (data) {
                    var err = new Error(data.error || 'Request failed');
                    err.status = response.status;
                    err.data = data;
                    throw err;
                }).catch(function (parseErr) {
                    if (parseErr.status) throw parseErr;
                    var err = new Error('Request failed');
                    err.status = response.status;
                    err.data = { error: 'Request failed' };
                    throw err;
                });
            }
            return response.json();
        });
};


/* --------------------------------------------------------------------------
 *  Bootstrap
 * ------------------------------------------------------------------------ */

document.addEventListener('DOMContentLoaded', function () {
    // Only auto-init if not on order page (order page calls SF.initOrderPage() itself)
    var cfg = window.SF_CONFIG || {};
    // The order page calls SF.initOrderPage() explicitly in its inline script,
    // so we only call SF.init() for non-order pages here.
    // We check if initOrderPage will be called by looking for the inline script marker.
    // A simpler approach: always call init() here — order page calls initOrderPage
    // which calls init() itself. So we guard against double-init.
    if (!document.querySelector('script[src$="storefront-checkout.js"]')) {
        // Not on order page — safe to auto-init
        SF.init();
    }
});
