const INSTALLED = Symbol("sickollie-interactions-installed");

function actionableTarget(event, root) {
    const element = event.target instanceof Element ? event.target : null;
    if (!element) return null;
    const direct = element.closest("button,[role='button'],summary,a[href],input[type='button'],input[type='submit']");
    if (direct && root.contains(direct) && !direct.matches(":disabled,[aria-disabled='true']")) return direct;
    const label = element.closest("label");
    if (label && root.contains(label) && label.querySelector("input[type='checkbox']:not(:disabled),input[type='radio']:not(:disabled)")) return label;
    return null;
}

export function installStudioInteractions(root, { pulse = 18 } = {}) {
    if (!root || root[INSTALLED]) return;
    root[INSTALLED] = true;
    root.addEventListener("pointerdown", event => {
        const target = actionableTarget(event, root);
        if (!target) return;
        try { navigator.vibrate?.(pulse); } catch (error) {}
        try {
            target.animate?.([
                { transform: "translateY(0) scale(1)", filter: "brightness(1)" },
                { transform: "translateY(1px) scale(.97)", filter: "brightness(1.16)" },
                { transform: "translateY(0) scale(1)", filter: "brightness(1)" },
            ], { duration: 120, easing: "ease-out" });
        } catch (error) {}
    }, { passive: true });
}
