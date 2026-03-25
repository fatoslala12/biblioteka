(function($) {
    'use strict';

    function FixSelectorHeight() {
        $('.selector .selector-chosen').each(function () {
            let selector_chosen = $(this);
            let selector_available = selector_chosen.siblings('.selector-available');

            let selector_chosen_select = selector_chosen.find('select').first();
            let selector_available_select = selector_available.find('select').first();
            let selector_available_filter = selector_available.find('p.selector-filter').first();

            selector_chosen_select.height(selector_available_select.height() + selector_available_filter.outerHeight());
            selector_chosen_select.css('border-top', selector_chosen_select.css('border-bottom'));
        });
    }

    function bs5Enabled() {
        return typeof window !== 'undefined' && window.bootstrap && typeof window.bootstrap.Tab === 'function';
    }

    function showTab($a) {
        const el = $a && $a.length ? $a.get(0) : null;
        if (!el) return;

        // Bootstrap 5 path (no jQuery plugins)
        if (bs5Enabled()) {
            window.bootstrap.Tab.getOrCreateInstance(el).show();
            return;
        }

        // Bootstrap 4 fallback (jQuery plugin)
        if ($.fn && typeof $.fn.tab === 'function') {
            $a.tab('show');
        }
    }

    function getCarouselInstance(el) {
        if (!el) return null;
        if (window.bootstrap && typeof window.bootstrap.Carousel === 'function') {
            return window.bootstrap.Carousel.getOrCreateInstance(el, { interval: false, ride: false, touch: true });
        }
        if ($.fn && typeof $(el).carousel === 'function') {
            return $(el);
        }
        return null;
    }

    function carouselTo($carousel, index) {
        const el = $carousel && $carousel.length ? $carousel.get(0) : null;
        const inst = getCarouselInstance(el);
        if (!inst) return;
        if (inst.to) inst.to(index);
        else inst.carousel(index);
    }

    function collapseAll($container) {
        const els = $('.panel-collapse', $container).toArray();
        if (window.bootstrap && typeof window.bootstrap.Collapse === 'function') {
            els.forEach((el) => {
                const inst = window.bootstrap.Collapse.getOrCreateInstance(el, { toggle: false });
                inst.hide();
            });
            return;
        }
        if ($.fn && typeof $.fn.collapse === 'function') {
            $('.panel-collapse', $container).collapse('hide');
        }
    }

    function collapseShow($el) {
        const el = $el && $el.length ? $el.get(0) : null;
        if (!el) return;
        if (window.bootstrap && typeof window.bootstrap.Collapse === 'function') {
            const inst = window.bootstrap.Collapse.getOrCreateInstance(el, { toggle: false });
            inst.show();
            return;
        }
        if ($.fn && typeof $el.collapse === 'function') {
            $el.collapse('show');
        }
    }

    function handleCarousel($carousel) {
        const errors = $('.errorlist li', $carousel);
        const hash = document.location.hash;

        // If we have errors, open that tab first
        if (errors.length) {
            const errorCarousel = errors.eq(0).closest('.carousel-item');
            carouselTo($carousel, errorCarousel.data('carouselid'));
            $('.carousel-fieldset-label', $carousel).text(errorCarousel.data()["label"]);
        } else if (hash) {
            // If we have a tab hash, open that
            const activeCarousel = $('.carousel-item[data-target="' + hash + '"]', $carousel);
            carouselTo($carousel, activeCarousel.data()["carouselid"]);
            $('.carousel-fieldset-label', $carousel).text(activeCarousel.data()["label"]);
        }

        // Update page hash/history on slide
        $carousel.on('slide.bs.carousel', function (e) {
            FixSelectorHeight();
            window.dispatchEvent(new Event('resize'));

            if (e.relatedTarget && e.relatedTarget.dataset && e.relatedTarget.dataset.hasOwnProperty("label")) {
                $('.carousel-fieldset-label', $carousel).text(e.relatedTarget.dataset.label);
            }
            const targetHash = e.relatedTarget && e.relatedTarget.dataset ? e.relatedTarget.dataset.target : null;
            if (!targetHash) return;

            if (history.pushState) history.pushState(null, null, targetHash);
            else location.hash = targetHash;
        });
    }

    function handleTabs($tabs) {
        const errors = $('.change-form .errorlist li');
        const hash = document.location.hash;

        // Siguro që Bootstrap 5 aktivizon tab-et e Jazzmin (data-toggle -> data-bs-toggle)
        $('a', $tabs).each(function () {
            const $a = $(this);
            if (!$a.attr('data-bs-toggle')) {
                const legacy = $a.attr('data-toggle');
                if (legacy) $a.attr('data-bs-toggle', legacy);
                else $a.attr('data-bs-toggle', 'tab');
            }
        });

        // Klikimi në tab (punon në BS5 edhe kur atributet ndryshojnë)
        $('a', $tabs).on('click', function (e) {
            e.preventDefault();
            showTab($(this));
        });

        // Nëse ka gabime, hap tab-in përkatës i pari
        if (errors.length) {
            const tabId = errors.eq(0).closest('.tab-pane').attr('id');
            showTab($('a[href="#' + tabId + '"]', $tabs));
        } else if (hash) {
            // If we have a tab hash, open that
            showTab($('a[href="' + hash + '"]', $tabs));
        }

        // Ruaj hash-in në URL për rifreskim faqeje
        $('a', $tabs).on('shown.bs.tab', function (e) {
            FixSelectorHeight();
            window.dispatchEvent(new Event('resize'));

            if (e && e.target && e.target.hash) {
                if (history.pushState) history.pushState(null, null, e.target.hash);
                else location.hash = e.target.hash;
            }
        });
    }

    function handleCollapsible($collapsible) {
        const errors = $('.errorlist li', $collapsible);
        const hash = document.location.hash;

        // Nëse ka gabime, hap seksionin përkatës i pari
        if (errors.length) {
            collapseAll($collapsible);
            collapseShow(errors.eq(0).closest('.panel-collapse'));
        } else if (hash) {
            // If we have a tab hash, open that
            collapseAll($collapsible);
            collapseShow($(hash, $collapsible));
        }

        // Ruaj hash-in në URL për rifreskim faqeje
        $collapsible.on('shown.bs.collapse', function (e) {
            FixSelectorHeight();
            window.dispatchEvent(new Event('resize'));

            if (e && e.target && e.target.id) {
                if (history.pushState) history.pushState(null, null, '#' + e.target.id);
                else location.hash = '#' + e.target.id;
            }
        });
    }

    function applySelect2() {
        // Apply select2 to any select boxes that don't yet have it
        // and are not part of the django's empty-form inline
        const noSelect2 = '.empty-form select, .select2-hidden-accessible, .selectfilter, .selector-available select, .selector-chosen select, select[data-autocomplete-light-function=select2]';
        $('select').not(noSelect2).select2({ width: 'element' });
    }

    $(document).ready(function () {
        const $carousel = $('#content-main form #jazzy-carousel');
        const $tabs = $('#content-main form #jazzy-tabs');
        const $collapsible = $('#content-main form #jazzy-collapsible');

        // Ensure all raw_id_fields have the search icon in them
        $('.related-lookup').append('<i class="fa fa-search"></i>');

        // Style the inline fieldset button
        $('.inline-related fieldset.module .add-row a').addClass('btn btn-sm btn-default float-right');
        $('div.add-row>a').addClass('btn btn-sm btn-default float-right');

        // Ensure we preserve the tab the user was on using the url hash, even on page reload
        if ($tabs.length) { handleTabs($tabs); }
        else if ($carousel.length) { handleCarousel($carousel); }
        else if ($collapsible.length) { handleCollapsible($collapsible); }

        applySelect2();

        $('body').on('change', '.related-widget-wrapper select', function(e) {
            const event = $.Event('django:update-related');
            $(this).trigger(event);
            if (!event.isDefaultPrevented() && typeof(window.updateRelatedObjectLinks) !== 'undefined') {
                updateRelatedObjectLinks(this);
            }
        });
    });

    // Apply select2 to all select boxes when new inline row is created
    django.jQuery(document).on('formset:added', applySelect2);

})(jQuery);

