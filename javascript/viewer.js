window.main_viewer_height = 512;


refresh_finished_images_catalog_label = function(translated_string) {
    if (!translated_string || translated_string === "") return;

    var attemptUpdate = function() {
        var accordion = document.querySelector('#finished_images_catalog');
        if (!accordion) return false;

        // Gradio 3 specifically likes to hide label text in .label or the first span
        var label = accordion.querySelector('.label span') ||
                    accordion.querySelector('.label') ||
                    accordion.querySelector('span');

        if (label && label.textContent !== translated_string) {
            label.textContent = translated_string;
            console.log("[Viewer] Startup Label Success: " + translated_string);
            return true;
        }
        return false;
    };

    // Run immediately
    if (attemptUpdate()) return;

    // If it fails (DOM not ready), try again every 500ms for 3 seconds
    var count = 0;
    var interval = setInterval(function() {
        count++;
        if (attemptUpdate() || count > 6) {
            clearInterval(interval);
        }
    }, 500);
};
window.refresh_finished_images_catalog_label = refresh_finished_images_catalog_label;


close_finished_images_catalog = function() {

    var accordion = document.getElementById('finished_images_catalog');
    if (!accordion) {
        console.log("[Viewer] The #finished_images_catalog was not found!");
        return;
    }

    // Find the <details> element (native HTML5 accordion)
    var details = (accordion.tagName.toUpperCase() === 'DETAILS') ? accordion : accordion.querySelector('details');

    if (details) {
        if (details.open) {
            var summary = accordion.querySelector('summary') || details.querySelector('summary');
            if (summary) {
                console.log("[Viewer] Clicking Catalogue summary to close native accordion...");
                summary.click();
            } else {
                console.log("[Viewer] Directly closing Catalogue details open property...");
                details.open = false;
                details.dispatchEvent(new Event('change'));
            }
        } else {
            console.log("[Viewer] The Catalogue accordion is already closed.");
        }
    } else {

        // Find the clickable header element using standard classes
        var toggleHeader = accordion.querySelector('.label-wrap') ||
                           accordion.querySelector('.label') ||
                           accordion.querySelector('span');

        if (toggleHeader) {
            // Check if the header container actually has the "open" class
            var isOpen = toggleHeader.classList.contains('open');

            if (isOpen) {
                console.log("[Viewer] The Catalogue Header is open. Clicking to close...");
                toggleHeader.click();
            } else {
                console.log("[Viewer] The Catalogue Header is already closed. No action taken.");
            }
        } else {
            console.log("[Viewer] Could not find any clickable header or details tag inside #finished_images_catalog.");
        }
    }
};
window.close_finished_images_catalog = close_finished_images_catalog;


function refresh_grid() {
    let gridContainer = document.querySelector('#final_gallery .grid-container');
    let final_gallery = document.getElementById('final_gallery');

    if (gridContainer) if (final_gallery) {
        let rect = final_gallery.getBoundingClientRect();
        let cols = Math.ceil((rect.width - 16.0) / rect.height);
        if (cols < 2) cols = 2;
        gridContainer.style.setProperty('--grid-cols', cols);
    }
}

function refresh_grid_delayed() {
    refresh_grid();
    setTimeout(refresh_grid, 100);
    setTimeout(refresh_grid, 500);
    setTimeout(refresh_grid, 1000);
}

function resized() {
    let windowHeight = window.innerHeight - 260;
    let elements = document.getElementsByClassName('main_view');

    if (windowHeight > 745) windowHeight = 745;

    for (let i = 0; i < elements.length; i++) {
        elements[i].style.height = windowHeight + 'px';
    }

    window.main_viewer_height = windowHeight;

    refresh_grid();
}

function viewer_to_top(delay = 100) {
    setTimeout(() => window.scrollTo({top: 0, behavior: 'smooth'}), delay);
}

function viewer_to_bottom(delay = 100) {
    let element = document.getElementById('positive_prompt');
    let yPos = window.main_viewer_height;

    if (element) {
        yPos = element.getBoundingClientRect().top + window.scrollY;
    }

    setTimeout(() => window.scrollTo({top: yPos - 8, behavior: 'smooth'}), delay);
}

window.addEventListener('resize', (e) => {
    resized();
});

onUiLoaded(async () => {
    resized();
});

function on_style_selection_blur() {
    let target = document.querySelector("#gradio_receiver_style_selections textarea");
    target.value = "on_style_selection_blur " + Math.random();
    let e = new Event("input", {bubbles: true})
    Object.defineProperty(e, "target", {value: target})
    target.dispatchEvent(e);
}

onUiLoaded(async () => {
    let spans = document.querySelectorAll('.aspect_ratios span');

    spans.forEach(function (span) {
        span.innerHTML = span.innerHTML.replace(/&lt;/g, '<').replace(/&gt;/g, '>');
    });

    document.querySelector('.style_selections').addEventListener('focusout', function (event) {
        setTimeout(() => {
            if (!this.contains(document.activeElement)) {
                on_style_selection_blur();
            }
        }, 200);
    });

    let inputs = document.querySelectorAll('.lora_weight input[type="range"]');

    inputs.forEach(function (input) {
        input.style.marginTop = '12px';
    });
});
