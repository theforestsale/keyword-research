document.addEventListener('DOMContentLoaded', function () {
    const form = document.getElementById('searchForm');
    const loading = document.getElementById('loading');
    const submitBtn = document.getElementById('submitBtn');

    if (form) {
        form.addEventListener('submit', function () {
            if (loading) loading.classList.remove('hidden');
            if (submitBtn) submitBtn.disabled = true;
        });
    }
});
