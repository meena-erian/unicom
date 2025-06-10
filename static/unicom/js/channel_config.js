// Function to get the editor once it's ready
function getEditor() {
    const editorElement = document.querySelector(".ace_editor");
    return editorElement?.env?.editor;
}

// Function to initialize our template functionality
function initializeTemplates() {
    const platformSelect = document.getElementById('id_platform');
    if (!platformSelect) return;

    const editor = getEditor();
    if (!editor) {
        setTimeout(initializeTemplates, 100);
        return;
    }

    const templates = {
        'Telegram': {
            "TELEGRAM_API_TOKEN": "your-bot-token-here"
        },
        'WhatsApp': {
            "PHONE_NUMBER": "your-whatsapp-number",
            "API_KEY": "your-api-key"
        },
        'Email': {
            "EMAIL_ADDRESS": "your-email@example.com",
            "EMAIL_PASSWORD": "your-email-password",
            "TRACKING_PARAMETER_ID": "unicom_tid",
            // MARK_SEEN_WHEN controls when emails are marked as seen in IMAP. Options: 'on_save', 'on_request_completed', 'on_request_completed' (default)
            "MARK_SEEN_WHEN": "on_request_completed"
        }
    };

    // Function to safely parse current config
    function getCurrentConfig() {
        try {
            const value = editor.getValue().trim();
            return value ? JSON.parse(value) : null;
        } catch (e) {
            return null;
        }
    }

    // Check if current config is just a template
    function isTemplate(config) {
        if (!config) return true;
        const configStr = JSON.stringify(config);
        return Object.values(templates).some(template => 
            JSON.stringify(template) === configStr
        );
    }

    function setTemplate(platform) {
        const template = templates[platform];
        if (template) {
            const json = JSON.stringify(template, null, 4);
            editor.setValue(json, -1);
            editor.clearSelection();
        }
    }

    platformSelect.addEventListener('change', function() {
        const currentConfig = getCurrentConfig();
        if (!currentConfig || isTemplate(currentConfig)) {
            setTemplate(this.value);
        }
    });

    // Set initial template if needed
    if (platformSelect.value) {
        const currentConfig = getCurrentConfig();
        if (!currentConfig || isTemplate(currentConfig)) {
            setTemplate(platformSelect.value);
        }
    }
}

// Start initialization when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    initializeTemplates();
}); 