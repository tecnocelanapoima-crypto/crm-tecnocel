/**
 * Tecnocel CRM — JavaScript principal
 * Funciones de utilidad para la interfaz
 */

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
        // Evitar doble instancia
        if (!bootstrap.Tooltip.getInstance(el)) {
            return new bootstrap.Tooltip(el, { 
                trigger: 'hover',
                delay: { "show": 300, "hide": 100 } // Pequeño retraso para que no sea molesto
            });
        }
    });
});

/**
 * Formatea un número como moneda colombiana
 * @param {number} valor
 * @returns {string}
 */
function formatearPrecioCOP(valor) {
    return '$ ' + valor.toLocaleString('es-CO', { minimumFractionDigits: 0 });
}
