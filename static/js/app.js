// Minimal DOM manipulation avoiding bulky frameworks.
document.addEventListener("DOMContentLoaded", function() {
    const forms = document.querySelectorAll('form');
    
    // Prevent duplicate processing submissions
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            const submitBtn = this.querySelector('button[type="submit"]');
            if(submitBtn && !submitBtn.disabled) {
                // Allows UI feedback ensuring user knows action is processing
                submitBtn.dataset.originalText = submitBtn.innerHTML;
                setTimeout(() => {
                    submitBtn.disabled = true;
                    submitBtn.innerHTML = 'Processing...';
                }, 0);
            }
        });
    });
});