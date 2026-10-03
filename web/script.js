const contentArea = document.getElementById('content-area');
const firstBtn = document.getElementById('first-btn');
const prevPageBtn = document.getElementById('prev-page-btn');
const prevBtn = document.getElementById('prev-btn');
const nextBtn = document.getElementById('next-btn');
const nextPageBtn = document.getElementById('next-page-btn');
const lastBtn = document.getElementById('last-btn');
const pageStepSelect = document.getElementById('page-step');
const autoScrollCitationsCheckbox = document.getElementById('auto-scroll-citations');
const autoScrollNotesCheckbox = document.getElementById('auto-scroll-notes');
const sourcePosition = document.getElementById('source-position');
const sourceProgress = document.getElementById('source-progress');
const progressTrack = document.querySelector('.progress-track');
const sections = Array.from(contentArea.querySelectorAll('.source-section'));
let currentIndex = 0;

function getPageStep() {
    return Number(pageStepSelect.value);
}

function scrollToPanel(selector) {
    const panel = sections[currentIndex].querySelector(selector);
    if (!panel) {
        return;
    }

    contentArea.style.paddingBottom = '0px';
    const panelTop = panel.getBoundingClientRect().top;
    const contentTop = contentArea.getBoundingClientRect().top;
    const targetScrollTop = contentArea.scrollTop + panelTop - contentTop;
    const maxScrollTop = contentArea.scrollHeight - contentArea.clientHeight;
    const extraBottomSpace = Math.max(0, targetScrollTop - maxScrollTop);
    contentArea.style.paddingBottom = `${extraBottomSpace}px`;
    contentArea.scrollTop = targetScrollTop;
}

function scrollToCitations() {
    scrollToPanel('.citations-panel');
}

function scrollToNotes() {
    scrollToPanel('.note-panel');
}

function showSection(index) {
    currentIndex = index;
    sections.forEach((section, sectionIndex) => {
        section.hidden = sectionIndex !== currentIndex;
    });
    contentArea.style.paddingBottom = '';
    contentArea.scrollTop = 0;
    if (autoScrollNotesCheckbox.checked) {
        scrollToNotes();
    } else if (autoScrollCitationsCheckbox.checked) {
        scrollToCitations();
    }
    firstBtn.disabled = index === 0;
    prevPageBtn.disabled = index === 0;
    prevBtn.disabled = index === 0;
    nextBtn.disabled = index === sections.length - 1;
    nextPageBtn.disabled = index === sections.length - 1;
    lastBtn.disabled = index === sections.length - 1;
    sourcePosition.textContent = `${index + 1} / ${sections.length}`;
    sourceProgress.style.width = `${((index + 1) / sections.length) * 100}%`;
    progressTrack.setAttribute('aria-valuemax', sections.length);
    progressTrack.setAttribute('aria-valuenow', index + 1);
}

autoScrollCitationsCheckbox.addEventListener('change', () => {
    if (autoScrollCitationsCheckbox.checked) {
        autoScrollNotesCheckbox.checked = false;
        scrollToCitations();
    } else {
        contentArea.style.paddingBottom = '';
    }
});

autoScrollNotesCheckbox.addEventListener('change', () => {
    if (autoScrollNotesCheckbox.checked) {
        autoScrollCitationsCheckbox.checked = false;
        scrollToNotes();
    } else {
        contentArea.style.paddingBottom = '';
    }
});

nextBtn.addEventListener('click', () => {
    if (currentIndex < sections.length - 1) {
        showSection(currentIndex + 1);
    }
});

firstBtn.addEventListener('click', () => {
    showSection(0);
});

prevBtn.addEventListener('click', () => {
    if (currentIndex > 0) {
        showSection(currentIndex - 1);
    }
});

prevPageBtn.addEventListener('click', () => {
    showSection(Math.max(0, currentIndex - getPageStep()));
});

nextPageBtn.addEventListener('click', () => {
    showSection(Math.min(sections.length - 1, currentIndex + getPageStep()));
});

lastBtn.addEventListener('click', () => {
    showSection(sections.length - 1);
});

if (sections.length === 0) {
    const message = document.createElement('p');
    message.textContent = 'Aucune source trouvée pour générer le rapport HTML.';
    contentArea.appendChild(message);
    firstBtn.disabled = true;
    prevPageBtn.disabled = true;
    prevBtn.disabled = true;
    nextBtn.disabled = true;
    nextPageBtn.disabled = true;
    lastBtn.disabled = true;
    pageStepSelect.disabled = true;
    autoScrollCitationsCheckbox.disabled = true;
    autoScrollNotesCheckbox.disabled = true;
    sourcePosition.textContent = '0 / 0';
} else {
    showSection(0);
}
