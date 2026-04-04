/**
 * Tecnocel CRM — JavaScript principal
 * Funciones de utilidad para la interfaz
 */

// ANTI-FOUC (Carga Inmediata de Tema Visual)
(function() {
    const theme = localStorage.getItem('crm_theme');
    if (theme && theme !== 'cyan') {
        document.documentElement.setAttribute('data-theme', theme);
    }
})();

/**
 * Muestra un diálogo de confirmación antes de eliminar un registro.
 * @param {string} nombre - Nombre del elemento a eliminar
 * @returns {boolean} true si el usuario confirmó, false si canceló
 */
function confirmarEliminar(nombre) {
    return confirm(`¿Estás seguro de que deseas eliminar "${nombre}"?\n\nEsta acción no se puede deshacer.`);
}

/**
 * Auto-cierre de alertas flash después de 5 segundos
 */
document.addEventListener('DOMContentLoaded', function () {
    // Auto-cerrar alertas después de 5 segundos
    const alertas = document.querySelectorAll('.alert.alert-success, .alert.alert-info');
    alertas.forEach(function (alerta) {
        setTimeout(function () {
            const bsAlert = bootstrap.Alert.getOrCreateInstance(alerta);
            if (bsAlert) bsAlert.close();
        }, 5000);
    });

    // Resaltar fila de tabla al pasar el mouse
    document.querySelectorAll('.table tbody tr').forEach(function (fila) {
        fila.style.cursor = 'pointer';
    });

    // Inyectar titles auto-generados a botones que no lo tengan para accesibilidad
    document.querySelectorAll('.btn, .nav-link').forEach(function(btn) {
        if (!btn.hasAttribute('title')) {
            let texto = btn.innerText.trim();
            
            // Si el botón no tiene texto (solo icono), deducir su función
            if (!texto) {
                if (btn.querySelector('.bi-trash')) texto = "Eliminar de forma permanente";
                else if (btn.querySelector('.bi-pencil')) texto = "Editar o ajustar datos";
                else if (btn.querySelector('.bi-eye')) texto = "Ver detalles completos";
                else if (btn.querySelector('.bi-receipt')) texto = "Ver la factura generada";
                else if (btn.querySelector('.bi-whatsapp')) texto = "Contactar al cliente";
                else if (btn.querySelector('.bi-download')) texto = "Descargar registro";
                else if (btn.querySelector('.bi-arrow-left')) texto = "Regresar al menú anterior";
                else if (btn.classList.contains('btn-close')) texto = "Cerrar ventana";
            }
            
            if (texto) {
                btn.setAttribute('title', texto);
            }
        }
    });

    // Ocultar titles nativos y mostrar Tooltips de Bootstrap interactivos en estos botones
    const tooltipTriggerList = [].slice.call(
        document.querySelectorAll('[title], [data-bs-toggle="tooltip"]')
    );
    tooltipTriggerList.map(function (el) {
        if (!bootstrap.Tooltip.getInstance(el)) {
            return new bootstrap.Tooltip(el, { trigger: 'hover', delay: { "show": 300, "hide": 100 } });
        }
    });

    // ── MOTOR DE CONFIGURACIÓN Y PERSONALIZACIÓN ──
    const themeSelectors = document.querySelectorAll('.theme-btn');
    const widgetToggles = document.querySelectorAll('.config-toggle');
    const resetBtn = document.getElementById('btnResetConfig');

    // 1. Cargar Theme guardado
    const currentTheme = localStorage.getItem('crm_theme') || 'cyan';
    document.documentElement.setAttribute('data-theme', currentTheme);
    themeSelectors.forEach(btn => {
        btn.classList.remove('active');
        if (btn.dataset.theme === currentTheme) {
            btn.classList.add('active');
            btn.style.borderColor = '#ffffff';
        } else {
            btn.style.borderColor = 'transparent';
        }
    });

    // 2. Cargar preferencias de Widgets
    let widgetState = JSON.parse(localStorage.getItem('crm_widgets')) || {};
    widgetToggles.forEach(toggle => {
        const targetId = toggle.dataset.target;
        const targetElement = document.getElementById(targetId);
        
        // Si el estado está guardado como false (oculto)
        if (widgetState[targetId] === false) {
            toggle.checked = false;
            if (targetElement) targetElement.classList.add('d-none');
        } else {
            // Predeterminado: Visible
            toggle.checked = true;
            if (targetElement) targetElement.classList.remove('d-none');
        }

        // Listener de cambio
        toggle.addEventListener('change', function() {
            const isVisible = this.checked;
            widgetState[targetId] = isVisible;
            localStorage.setItem('crm_widgets', JSON.stringify(widgetState));
            
            if (targetElement) {
                if (isVisible) targetElement.classList.remove('d-none');
                else targetElement.classList.add('d-none');
            }
        });
    });

    // 3. Listener para cambio de Theme
    themeSelectors.forEach(btn => {
        btn.addEventListener('click', function() {
            const newTheme = this.dataset.theme;
            localStorage.setItem('crm_theme', newTheme);
            document.documentElement.setAttribute('data-theme', newTheme);
            
            // Actualizar interfaz del selector
            themeSelectors.forEach(b => {
                b.classList.remove('active');
                b.style.borderColor = 'transparent';
            });
            this.classList.add('active');
            this.style.borderColor = '#ffffff';
        });
    });

    // 4. Restablecer Configuración
    if (resetBtn) {
        resetBtn.addEventListener('click', function() {
            if (confirm('¿Restablecer tema y módulos a la vista de fábrica?')) {
                localStorage.removeItem('crm_theme');
                localStorage.removeItem('crm_widgets');
                window.location.reload();
            }
        });
    }
});

/**
 * Formatea un número como moneda colombiana
 * @param {number} valor
 * @returns {string}
 */
function formatearPrecioCOP(valor) {
    return '$ ' + valor.toLocaleString('es-CO', { minimumFractionDigits: 0 });
}
