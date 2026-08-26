/** @type {import('@docusaurus/plugin-content-docs').SidebarsConfig} */
const sidebars = {
  tutorialSidebar: [
    'intro',
    {
      type: 'category',
      label: 'Arquitectura',
      items: [
        'architecture/observabilidad-sprint-1',
        'architecture/performance-escalabilidad-sprint-2',
        'architecture/resiliencia-operativa-sprint-3',
        'architecture/gate-go-no-go',
        'architecture/devsecops-enterprise',
        'architecture/politica-security-scan',
        'architecture/sre-operacion-enterprise',
        'architecture/dr-continuidad-enterprise',
        'architecture/matriz-madurez-enterprise'
      ]
    },
    {
      type: 'category',
      label: 'Procesos',
      items: [
        'procesos/procesos-indice',
        'procesos/procesos-onboarding-gobierno-inicial',
        'procesos/procesos-maestros-comerciales-directorio',
        'procesos/procesos-inventario-y-bodegas',
        'procesos/procesos-compras-cxp-retenciones',
        'procesos/procesos-ventas-cxc-facturacion-electronica',
        'procesos/procesos-impresion-comprobantes',
        'procesos/procesos-reporteria-control-gerencial'
      ]
    },
    {
      type: 'category',
      label: 'API',
      items: [
        'api/cobertura-total-endpoints',
        {
          type: 'category',
          label: 'Common',
          items: [
            'api/common/onboarding',
            'api/common/seguridad-accesos',
            'api/common/empresa-seleccionada-sesion',
            'api/common/directorio'
          ]
        },
        {
          type: 'category',
          label: 'Inventario',
          items: [
            'api/inventario/checklist-integracion-frontend',
            'api/inventario/bloques-construccion',
            'api/inventario/casa-comercial-bodega',
            'api/inventario/producto-atributos-impuestos-bodegas',
            'api/inventario/producto-crud-base'
          ]
        }
        ,
        {
          type: 'category',
          label: 'Transacciones',
          items: [
            'api/transacciones/compras',
            {
              type: 'category',
              label: 'Ventas',
              items: [
                'api/transacciones/ventas/checklist-integracion-frontend',
                'api/transacciones/ventas/ventas-ciclo-comercial',
                'api/transacciones/ventas/facturacion-electronica-y-documentos'
              ]
            }
          ]
        },
        {
          type: 'category',
          label: 'SRI',
          items: [
            'api/sri/checklist-integracion-frontend',
            'api/sri/core-sri-contratos',
            'api/sri/catalogo-impuestos',
            'api/sri/facturacion-electronica-cola-documentos'
          ]
        },
        {
          type: 'category',
          label: 'Impresión',
          items: [
            'api/impresion/checklist-integracion-frontend',
            'api/impresion/matriz-pantallas-endpoints',
            'api/impresion/impresion-documentos-y-reimpresion'
          ]
        },
        {
          type: 'category',
          label: 'Reportes',
          items: [
            'api/reportes/checklist-integracion-frontend',
            'api/reportes/matriz-pantallas-endpoints',
            'api/reportes/ventas-y-rentabilidad',
            'api/reportes/operativos-tributarios'
          ]
        }
      ]
    }
  ]
};

module.exports = sidebars;
