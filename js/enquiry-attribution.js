// Keep campaign labels with the enquiry. Native form submission also works without this script.
const enquiryParameters = new URLSearchParams(window.location.search);
document.querySelectorAll('[data-enquiry-form]').forEach(form => {
    ['utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content'].forEach(name => {
        const field = form.elements.namedItem(name);
        if (field && enquiryParameters.has(name)) {
            field.value = enquiryParameters.get(name).slice(0, 200);
        }
    });
});
