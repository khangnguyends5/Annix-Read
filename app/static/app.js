/*  Annix Read — book page interactivity.
 *
 *  Drives the controls on /book/:id : generate a summary, switch language,
 *  trigger TTS audio playback, and enable PDF / EPUB downloads.
 */

(function () {
    const article = document.querySelector('article[data-book-id]');
    if (!article) return;  // not on a book page

    const bookId    = parseInt(article.dataset.bookId, 10);
    const $lang     = document.getElementById('lang-select');
    const $btnGen   = document.getElementById('btn-generate');
    const $btnAud   = document.getElementById('btn-audio');
    const $btnPdf   = document.getElementById('btn-pdf');
    const $btnEpub  = document.getElementById('btn-epub');
    const $status   = document.getElementById('status');
    const $summary  = document.getElementById('summary');
    const $player   = document.getElementById('player');

    // Has the English summary been generated yet? (Server-rendered as #summary-md.)
    let hasEnglishSummary = !!document.getElementById('summary-md');

    // Cache of {lang: contentHtml} so switching language is instant after first fetch.
    const contentCache = {};
    if (hasEnglishSummary) {
        contentCache['en'] = document.getElementById('summary-md').innerText;
    }

    function setStatus(message, type) {
        if (!message) { $status.classList.add('hidden'); return; }
        $status.classList.remove('hidden');
        $status.textContent = message;
        const colors = {
            info:    'bg-blue-50  text-blue-800  border border-blue-200',
            success: 'bg-green-50 text-green-800 border border-green-200',
            error:   'bg-red-50   text-red-800   border border-red-200',
            working: 'bg-amber-50 text-amber-800 border border-amber-200',
        };
        $status.className = 'mb-4 px-4 py-3 rounded-md text-sm ' + (colors[type] || colors.info);
    }

    function setExportsEnabled(enabled) {
        for (const btn of [$btnAud, $btnPdf, $btnEpub]) {
            if (enabled) {
                btn.classList.remove('opacity-60', 'pointer-events-none');
                btn.disabled = false;
            } else {
                btn.classList.add('opacity-60', 'pointer-events-none');
                btn.disabled = true;
            }
        }
    }

    function updateExportLinks() {
        const lang = $lang.value;
        $btnPdf.href  = `/api/books/${bookId}/export.pdf?lang=${lang}`;
        $btnEpub.href = `/api/books/${bookId}/export.epub?lang=${lang}`;
    }

    // Tiny Markdown -> HTML for rendering the summary in the page.
    function renderMarkdown(md) {
        const lines = md.split('\n');
        let html = '';
        let inList = false, listType = null;
        const closeList = () => {
            if (inList) { html += `</${listType}>`; inList = false; listType = null; }
        };
        const inline = s => s
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.+?)\*/g, '<em>$1</em>')
            .replace(/__(.+?)__/g, '<strong>$1</strong>')
            .replace(/_(.+?)_/g, '<em>$1</em>')
            .replace(/`([^`]+)`/g, '<code>$1</code>');

        let para = [];
        const flushPara = () => {
            if (para.length) {
                html += `<p>${inline(para.join(' '))}</p>`;
                para = [];
            }
        };

        for (const raw of lines) {
            const line = raw.trim();
            if (!line) { flushPara(); closeList(); continue; }
            const h = line.match(/^(#{1,6})\s+(.*)/);
            const ul = line.match(/^[-*+]\s+(.*)/);
            const ol = line.match(/^\d+\.\s+(.*)/);
            if (h) {
                flushPara(); closeList();
                const level = Math.min(h[1].length, 3);
                html += `<h${level}>${inline(h[2])}</h${level}>`;
            } else if (ul) {
                flushPara();
                if (!inList || listType !== 'ul') { closeList(); html += '<ul>'; inList = true; listType = 'ul'; }
                html += `<li>${inline(ul[1])}</li>`;
            } else if (ol) {
                flushPara();
                if (!inList || listType !== 'ol') { closeList(); html += '<ol>'; inList = true; listType = 'ol'; }
                html += `<li>${inline(ol[1])}</li>`;
            } else {
                closeList();
                para.push(line);
            }
        }
        flushPara(); closeList();
        return html;
    }

    function showContent(lang, content) {
        contentCache[lang] = content;
        const words = content.split(/\s+/).filter(Boolean).length;
        const readMin = Math.max(1, Math.round(words / 200));
        $summary.innerHTML = `
            <div class="text-xs text-stone-400 mb-2">${words} words · ~${readMin} min read · ${lang.toUpperCase()}</div>
            <div id="summary-md">${renderMarkdown(content)}</div>
        `;
    }

    // ─── Generate / switch language ───────────────────────────────────────
    async function ensureContentForLang(lang) {
        if (contentCache[lang]) {
            showContent(lang, contentCache[lang]);
            return contentCache[lang];
        }

        // Need at least the English summary first.
        if (!hasEnglishSummary) {
            setStatus('Generating English summary with Claude (may take 30–90 seconds)...', 'working');
            const res = await fetch(`/api/books/${bookId}/summary`, { method: 'POST' });
            if (!res.ok) throw new Error((await res.json()).detail || 'Summary failed');
            const data = await res.json();
            contentCache['en'] = data.content;
            hasEnglishSummary = true;
            setStatus('Summary ready.', 'success');
            setTimeout(() => setStatus(''), 2000);
        }

        if (lang === 'en') {
            showContent('en', contentCache['en']);
            return contentCache['en'];
        }

        // Try cached translation on server first
        const tryRes = await fetch(`/api/books/${bookId}/translation?lang=${lang}`);
        if (tryRes.ok) {
            const data = await tryRes.json();
            showContent(lang, data.content);
            return data.content;
        }

        setStatus(`Translating to ${$lang.options[$lang.selectedIndex].text}...`, 'working');
        const res = await fetch(`/api/books/${bookId}/translation?lang=${lang}`, { method: 'POST' });
        if (!res.ok) throw new Error((await res.json()).detail || 'Translation failed');
        const data = await res.json();
        showContent(lang, data.content);
        setStatus('Translation ready.', 'success');
        setTimeout(() => setStatus(''), 2000);
        return data.content;
    }

    $btnGen.addEventListener('click', async () => {
        $btnGen.disabled = true;
        try {
            await ensureContentForLang($lang.value);
            setExportsEnabled(true);
            updateExportLinks();
        } catch (err) {
            setStatus('❌ ' + err.message, 'error');
        } finally {
            $btnGen.disabled = false;
        }
    });

    $lang.addEventListener('change', async () => {
        if (!hasEnglishSummary) return;  // user must generate first
        try {
            await ensureContentForLang($lang.value);
            updateExportLinks();
        } catch (err) {
            setStatus('❌ ' + err.message, 'error');
        }
    });

    $btnAud.addEventListener('click', async () => {
        if (!hasEnglishSummary) {
            setStatus('Generate the summary first.', 'error');
            return;
        }
        const lang = $lang.value;
        // Make sure the translation exists for non-English audio.
        if (lang !== 'en' && !contentCache[lang]) {
            try { await ensureContentForLang(lang); }
            catch (err) { setStatus('❌ ' + err.message, 'error'); return; }
        }
        setStatus('Synthesizing audio...', 'working');
        $player.src = `/api/books/${bookId}/audio?lang=${lang}&t=${Date.now()}`;
        $player.classList.remove('hidden');
        $player.play().catch(() => { /* autoplay sometimes blocked; user can click play */ });
        $player.addEventListener('loadeddata', () => {
            setStatus('Audio ready.', 'success');
            setTimeout(() => setStatus(''), 2000);
        }, { once: true });
        $player.addEventListener('error', () => {
            setStatus('❌ Audio generation failed. Check server logs.', 'error');
        }, { once: true });
    });

    // Initial state
    if (hasEnglishSummary) {
        setExportsEnabled(true);
        updateExportLinks();
        // Render the server-side Markdown text through the same pipeline.
        const raw = document.getElementById('summary-md').innerText;
        showContent('en', raw);
    } else if (article.dataset.autoGenerate === '1') {
        // Auto-trigger generation when arriving via the "request a new book" flow.
        $btnGen.click();
    }
})();
