/*
 * Global utility to initialise TinyMCE editors across the Unicom admin.
 * Usage:
 *   UnicomTinyMCE.init('#selector', {
 *       // Any TinyMCE config overrides.
 *       setup: function (editor) {
 *           // Called when the editor instance is ready.
 *       }
 *   });
 */
(function (global) {
    'use strict';

    if (!global) {
        return;
    }

    const DEFAULT_CONFIG = {
        plugins: 'link image lists table code',
        toolbar: 'undo redo | blocks | bold italic | alignleft aligncenter alignright | indent outdent | bullist numlist | code | table',
        height: 400,
        max_height: 400,
        menubar: false,
        branding: false,
        promotion: false,
        /*
         * We will attach a default setup that triggers save on change so that the underlying
         * <textarea> is always kept in sync.
         */
        setup: function (ed) {
            ed.on('change', function () {
                ed.save();
            });
        }
    };

    function mergeConfigs(base, overrides) {
        if (!overrides) return Object.assign({}, base);

        const merged = Object.assign({}, base, overrides);

        // If user supplied a custom setup, wrap it so both run.
        if (typeof overrides.setup === 'function') {
            const userSetup = overrides.setup;
            merged.setup = function (ed) {
                if (typeof base.setup === 'function') {
                    base.setup(ed);
                }
                userSetup(ed);
            };
        }

        return merged;
    }

    function removeExisting(selector) {
        // Remove any editor targeting the same element (if one already exists).
        if (!global.tinymce || !global.tinymce.editors) return;
        // Iterate over a copy of the array in case removing an editor modifies the collection.
        [...global.tinymce.editors].forEach(function (ed) {
            if (ed.targetElm && ('#' + ed.targetElm.id) === selector) {
                ed.remove();
            }
        });
    }

    function init(selector, overrides) {
        function actuallyInit() {
            removeExisting(selector);
            const config = mergeConfigs(DEFAULT_CONFIG, overrides);
            // Ensure selector always matches passed element.
            config.selector = selector;
            return global.tinymce.init(config);
        }

        // TinyMCE may not be loaded yet if our helper is referenced before the CDN script executes.
        if (global.tinymce && global.tinymce.init) {
            return actuallyInit();
        }

        // Otherwise, poll a few times until TinyMCE becomes available.
        return new Promise(function (resolve, reject) {
            const maxAttempts = 50; // ±5 seconds at 100 ms interval
            let attempts = 0;
            const interval = setInterval(function () {
                if (global.tinymce && global.tinymce.init) {
                    clearInterval(interval);
                    resolve(actuallyInit());
                } else if (++attempts >= maxAttempts) {
                    clearInterval(interval);
                    console.error('TinyMCE did not load in time.');
                    reject(new Error('TinyMCE not loaded'));
                }
            }, 100);
        });
    }

    global.UnicomTinyMCE = {
        init: init,
        defaultConfig: DEFAULT_CONFIG
    };
})(window); 