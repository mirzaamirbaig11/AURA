// AURA Main JavaScript
(function () {
    'use strict';

    const CSRF = window.AURA_CSRF || (document.querySelector('meta[name="csrf-token"]') || {}).content || '';

    /* ---------------- jQuery AJAX: CSRF + JSON ---------------- */
    if (window.jQuery) {
        jQuery.ajaxSetup({ headers: { 'X-CSRFToken': CSRF } });
        // Legacy calls do $.post(url, JSON.stringify({...})) — send them as real JSON
        jQuery.ajaxPrefilter(function (opts) {
            if (typeof opts.data === 'string' && /^\s*[\[{]/.test(opts.data)) {
                opts.contentType = 'application/json';
            }
        });
    }

    /* ---------------- Toasts ---------------- */
    const ICONS = { success: 'fa-circle-check', danger: 'fa-circle-exclamation', error: 'fa-circle-exclamation', warning: 'fa-triangle-exclamation', info: 'fa-circle-info' };

    function dismissToast(el) {
        if (!el || el.classList.contains('hide')) return;
        el.classList.add('hide');
        setTimeout(() => el.remove(), 240);
    }

    function wireToast(el) {
        const btn = el.querySelector('.toast-close');
        if (btn) btn.addEventListener('click', () => dismissToast(el));
        const ttl = el.classList.contains('danger') || el.classList.contains('error') ? 7000 : 4500;
        setTimeout(() => dismissToast(el), ttl);
    }

    window.showToast = function (message, type) {
        type = type || 'info';
        let box = document.getElementById('aura-toasts');
        if (!box) {
            box = document.createElement('div');
            box.id = 'aura-toasts';
            box.className = 'aura-toasts';
            box.setAttribute('aria-live', 'polite');
            document.body.appendChild(box);
        }
        const el = document.createElement('div');
        el.className = 'aura-toast ' + type;
        el.setAttribute('role', 'status');
        el.innerHTML = '<i class="fas ' + (ICONS[type] || ICONS.info) + ' lead-icon"></i><div></div>' +
            '<button type="button" class="toast-close" aria-label="Close"><i class="fas fa-xmark"></i></button>';
        el.querySelector('div').textContent = message;
        box.appendChild(el);
        wireToast(el);
    };

    /* ---------------- Helpers ---------------- */
    function postJSON(url, body) {
        return fetch(url, {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': CSRF, 'X-Requested-With': 'XMLHttpRequest' },
            body: JSON.stringify(body || {})
        }).then(r => r.json().catch(() => ({ success: false, message: 'Something went wrong' })));
    }

    window.updateCartCount = function () {
        fetch('/api/cart', { credentials: 'same-origin', headers: { 'Accept': 'application/json' } })
            .then(r => (r.ok && (r.headers.get('content-type') || '').includes('json')) ? r.json() : null)
            .then(data => {
                const count = data && data.count ? data.count : 0;
                document.querySelectorAll('#cart-count, .cart-count-badge').forEach(b => {
                    b.textContent = count > 99 ? '99+' : count;
                    b.classList.toggle('d-none', !count);
                });
            })
            .catch(() => {});
    };

    window.addToCart = function (productId, sizeId, quantity) {
        return postJSON('/api/cart/add', { product_id: productId, size_id: sizeId, quantity: quantity || 1 })
            .then(res => {
                showToast(res.message || (res.success ? 'Added to cart' : 'Could not add to cart'), res.success ? 'success' : 'danger');
                if (res.success) updateCartCount();
                return res;
            })
            .catch(() => showToast('Please log in to add items to your cart.', 'warning'));
    };

    /* ---------------- Init ---------------- */
    document.addEventListener('DOMContentLoaded', function () {
        // Server-rendered flash toasts
        document.querySelectorAll('.aura-toast').forEach(wireToast);

        // Cart badge
        updateCartCount();

        // Newsletter (any form with id/class newsletter-form)
        document.querySelectorAll('#newsletter-form, .newsletter-form').forEach(form => {
            form.addEventListener('submit', function (e) {
                e.preventDefault();
                const input = form.querySelector('input[name="email"]');
                const btn = form.querySelector('button[type="submit"]');
                if (!input || !input.value) return;
                btn && btn.classList.add('is-loading');
                postJSON('/api/newsletter/subscribe', { email: input.value })
                    .then(res => {
                        showToast(res.message || 'Subscribed!', res.success ? 'success' : 'danger');
                        if (res.success) input.value = '';
                    })
                    .finally(() => btn && btn.classList.remove('is-loading'));
            });
        });

        // Size selection (legacy .size-option buttons)
        document.addEventListener('click', function (e) {
            const opt = e.target.closest('.size-option');
            if (!opt || opt.disabled || opt.classList.contains('disabled')) return;
            opt.parentElement.querySelectorAll('.size-option').forEach(o => o.classList.remove('active'));
            opt.classList.add('active');
        });

        // Quantity steppers: <div class="qty-stepper"><button data-step="-1">…<input>…<button data-step="1">
        document.addEventListener('click', function (e) {
            const b = e.target.closest('.qty-stepper [data-step]');
            if (!b) return;
            const input = b.parentElement.querySelector('input');
            const min = parseInt(input.min || '1', 10), max = parseInt(input.max || '99', 10);
            const v = Math.min(max, Math.max(min, (parseInt(input.value, 10) || min) + parseInt(b.dataset.step, 10)));
            input.value = v;
            input.dispatchEvent(new Event('change', { bubbles: true }));
        });

        // Show / hide password on every password field
        document.querySelectorAll('input[type="password"]').forEach(inp => {
            if (inp.dataset.noToggle !== undefined) return;
            const wrap = document.createElement('div');
            wrap.className = 'position-relative';
            inp.parentNode.insertBefore(wrap, inp);
            wrap.appendChild(inp);
            inp.style.paddingRight = '2.6rem';
            const t = document.createElement('button');
            t.type = 'button';
            t.className = 'password-toggle';
            t.setAttribute('aria-label', 'Show password');
            t.innerHTML = '<i class="far fa-eye"></i>';
            t.addEventListener('click', () => {
                const show = inp.type === 'password';
                inp.type = show ? 'text' : 'password';
                t.innerHTML = show ? '<i class="far fa-eye-slash"></i>' : '<i class="far fa-eye"></i>';
                t.setAttribute('aria-label', show ? 'Hide password' : 'Show password');
            });
            wrap.appendChild(t);
        });

        // Loading state on normal (non-AJAX) form submits
        document.querySelectorAll('form').forEach(form => {
            if (form.matches('#newsletter-form, .newsletter-form, [data-no-loading]')) return;
            form.addEventListener('submit', function () {
                if (form.dataset.ajax !== undefined) return;
                const btn = form.querySelector('button[type="submit"], input[type="submit"]');
                if (btn && form.checkValidity()) {
                    setTimeout(() => btn.classList.add('is-loading'), 0);
                    setTimeout(() => btn.classList.remove('is-loading'), 8000); // safety
                }
            });
        });

        // Image fallback for broken product images
        document.querySelectorAll('img[data-fallback]').forEach(img => {
            img.addEventListener('error', function onErr() {
                img.removeEventListener('error', onErr);
                img.src = img.dataset.fallback;
            });
        });

        // Scroll reveal
        const items = document.querySelectorAll('.reveal');
        if ('IntersectionObserver' in window && items.length) {
            const io = new IntersectionObserver(entries => {
                entries.forEach(en => {
                    if (en.isIntersecting) { en.target.classList.add('in'); io.unobserve(en.target); }
                });
            }, { threshold: 0.12 });
            items.forEach(i => io.observe(i));
        } else {
            items.forEach(i => i.classList.add('in'));
        }
    });
})();
