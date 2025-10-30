document.addEventListener('DOMContentLoaded', () => {
    const checkForm = document.getElementById('check-form');
    const resultsDiv = document.getElementById('results');
    const loader = document.getElementById('loader');

    checkForm.addEventListener('submit', async (event) => {
        event.preventDefault();
        const query = document.getElementById('query').value;
        const location = document.getElementById('location').value;
        const device = document.querySelector('input[name="device"]:checked').value;
        resultsDiv.innerHTML = '';
        loader.classList.remove('hidden');
        const payload = { query, device, location: location || null };
        try {
            const response = await fetch('/v1/check', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
            if (!response.ok) { const errorData = await response.json(); throw new Error(errorData.detail || 'API sunucusunda bir hata oluştu.'); }
            const data = await response.json();
            displayResults(data);
        } catch (error) {
            resultsDiv.innerHTML = `<div class="result-message error">Hata: ${error.message}</div>`;
        } finally {
            loader.classList.add('hidden');
        }
    });

    function displayResults(data) {
        resultsDiv.innerHTML = '';
        if (data.has_ads) {
            let html = `<h3>"${data.query}" için ${data.ads_count} adet reklam bulundu:</h3>`;
            data.ads.forEach(ad => { html += `<div class="ad-item"><h3>${ad.title || 'Başlık Yok'}</h3><p>${ad.url || 'URL Yok'}</p></div>`; });
            resultsDiv.innerHTML = html;
        } else {
            resultsDiv.innerHTML = `<div class="result-message success">"${data.query}" için reklam bulunamadı.</div>`;
        }
    }

    const jobForm = document.getElementById('job-form');
    const jobList = document.getElementById('job-list');

    async function loadJobs() {
        try {
            const response = await fetch('/v1/jobs');
            if (!response.ok) throw new Error('Görevler sunucudan alınamadı.');
            const jobs = await response.json();
            jobList.innerHTML = '';
            if (jobs.length === 0) { jobList.innerHTML = '<li>Aktif zamanlanmış görev bulunmuyor.</li>'; return; }
            jobs.forEach(job => {
                const li = document.createElement('li');
                li.innerHTML = `<span><strong>${job.query}</strong> (${job.location || 'Genel'}) - ${job.interval_minutes} dakikada bir</span><button class="delete-job" data-id="${job.id}">Sil</button>`;
                jobList.appendChild(li);
            });
        } catch (error) {
            console.error('Görevler yüklenirken hata:', error);
            jobList.innerHTML = '<li>Görevler yüklenemedi.</li>';
        }
    }

    jobForm.addEventListener('submit', async (event) => {
        event.preventDefault();
        const payload = {
            query: document.getElementById('job-query').value,
            location: document.getElementById('job-location').value || null,
            interval_minutes: parseInt(document.getElementById('job-interval').value, 10),
            device: 'desktop'
        };
        try {
            const response = await fetch('/v1/jobs', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload) });
            if (!response.ok) throw new Error('Görev eklenemedi.');
            jobForm.reset();
            loadJobs();
        } catch (error) {
            alert('Görev eklenirken bir hata oluştu: ' + error.message);
        }
    });

    jobList.addEventListener('click', async (event) => {
        if (event.target.classList.contains('delete-job')) {
            const jobId = event.target.dataset.id;
            if (confirm('Bu görevi silmek istediğinizden emin misiniz?')) {
                try {
                    const response = await fetch(`/v1/jobs/${jobId}`, { method: 'DELETE' });
                    if (!response.ok) throw new Error('Görev silinemedi.');
                    loadJobs();
                } catch (error) {
                    alert('Görevi silerken bir hata oluştu: ' + error.message);
                }
            }
        }
    });
    loadJobs();
});