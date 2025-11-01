(function (global) {
  'use strict';

  function ready(fn) {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', fn);
    } else {
      fn();
    }
  }

  function safeDateValue(value) {
    if (!value) {
      return null;
    }
    const date = new Date(value);
    return isNaN(date.getTime()) ? null : date;
  }

  ready(function () {
    const form = document.getElementById('communication-compose-form');
    if (!form) {
      return;
    }

    const timezoneInput = document.getElementById('compose-timezone');
    const channelSelect = document.getElementById('id_channel');
    const subjectInput = document.getElementById('id_subject_template');
    const sendAtInput = document.getElementById('id_send_at');
    const deliveryRadios = Array.from(document.querySelectorAll('input[name="delivery_mode"]'));
    const scheduleWrapper = document.querySelector('[data-delivery-schedule]');
    const submitButton = document.getElementById('compose-submit');
    const advancedToggle = document.querySelector('.toggle-advanced');
    const advancedSectionSelector = advancedToggle ? advancedToggle.getAttribute('data-target') : null;
    const advancedSection = advancedSectionSelector ? document.querySelector(advancedSectionSelector) : null;

    if (timezoneInput && !timezoneInput.value && global.Intl && global.Intl.DateTimeFormat) {
      timezoneInput.value = global.Intl.DateTimeFormat().resolvedOptions().timeZone;
    }

    if (advancedToggle && advancedSection) {
      advancedToggle.addEventListener('click', function () {
        advancedSection.classList.toggle('active');
      });
    }

    let editorInstance = null;

    function initEditor(channelId) {
      if (!global.UnicomTinyMCE || !global.UnicomTinyMCE.init) {
        return;
      }
      global.UnicomTinyMCE.init('#id_content', {
        channel_id: channelId || null,
        setup: function (editor) {
          editorInstance = editor;
        }
      });
    }

    function teardownEditor() {
      if (!global.tinymce || !editorInstance) {
        return;
      }
      editorInstance.remove();
      editorInstance = null;
    }

    function getCurrentChannelId() {
      return channelSelect && channelSelect.value ? channelSelect.value : null;
    }

    function updateButtonLabel() {
      if (!submitButton) {
        return;
      }
      const scheduleDate = safeDateValue(sendAtInput ? sendAtInput.value : null);
      if (scheduleDate) {
        submitButton.textContent = 'Schedule for ' + scheduleDate.toLocaleString();
      } else {
        submitButton.textContent = 'Send now';
      }
    }

    function ensureDeliveryMode() {
      if (!sendAtInput || !deliveryRadios.length) {
        return;
      }
      const scheduleSelected = !!sendAtInput.value;
      deliveryRadios.forEach(function (radio) {
        if (radio.value === 'schedule') {
          radio.checked = scheduleSelected;
        } else if (radio.value === 'now') {
          radio.checked = !scheduleSelected;
        }
      });
      if (scheduleWrapper) {
        scheduleWrapper.classList.toggle('active', scheduleSelected);
      }
      if (scheduleSelected) {
        sendAtInput.setAttribute('required', 'required');
      } else {
        sendAtInput.removeAttribute('required');
        sendAtInput.value = '';
      }
      updateButtonLabel();
    }

    if (deliveryRadios.length) {
      deliveryRadios.forEach(function (radio) {
        radio.addEventListener('change', function () {
          if (radio.value === 'schedule') {
            if (scheduleWrapper) {
              scheduleWrapper.classList.add('active');
            }
            sendAtInput.setAttribute('required', 'required');
          } else {
            if (scheduleWrapper) {
              scheduleWrapper.classList.remove('active');
            }
            sendAtInput.removeAttribute('required');
            sendAtInput.value = '';
          }
          updateButtonLabel();
        });
      });
    }

    if (sendAtInput) {
      sendAtInput.addEventListener('change', updateButtonLabel);
    }

    if (subjectInput) {
      subjectInput.addEventListener('input', function () {
        subjectInput.dataset.userEdited = '1';
      });
    }

    function maybeToggleAdvancedOnErrors() {
      if (!advancedSection) {
        return;
      }
      const hasValue = sendAtInput && sendAtInput.value;
      const hasSubject = subjectInput && subjectInput.value;
      const errorsPresent = advancedSection.querySelector('.field-errors');
      if (hasValue || hasSubject || errorsPresent) {
        advancedSection.classList.add('active');
      }
    }

    function onChannelChange() {
      teardownEditor();
      initEditor(getCurrentChannelId());
    }

    if (channelSelect) {
      channelSelect.addEventListener('change', onChannelChange);
    }

    maybeToggleAdvancedOnErrors();
    initEditor(getCurrentChannelId());
    ensureDeliveryMode();
    updateButtonLabel();
  });
})(window);
