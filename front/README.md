# MAIA SPINE - Frontend para Análisis de Escoliosis

Interface web para el sistema de diagnóstico de escoliosis basado en CNN y TDA.

## Descripción

Esta aplicación proporciona una interfaz moderna para cargar, analizar y visualizar radiografías de columna vertebral. Se conecta con el backend FastAPI del repositorio [MAIA-SPINE-ANATOMIC_MANIFOLD_CNN_TDA](https://github.com/oesquivel81/MAIA-SPINE-ANATOMIC_MANIFOLD_CNN_TDA.git).

## Características

- **Carga de imágenes**: Interfaz drag-and-drop para subir radiografías
- **Visualización de imágenes**: Visor con zoom y rotación para radiografías
- **Diagrama de columna**: Visualización interactiva de vértebras
- **Tabla de mediciones**: Métricas detalladas con rangos normales y alertas
- **Visualización 3D**: Mapa de calor interactivo de la columna vertebral
- **Normalización de imágenes**: Procesamiento automático mediante API backend

## Tecnologías

- React 18.3.1
- TypeScript
- Material UI 7.3.5
- Tailwind CSS 4.1.12
- Lucide React (iconos)
- Sonner (notificaciones)
- Vite 6.3.5

## Estructura del Proyecto

```
src/
├── app/
│   ├── App.tsx                         # Componente principal
│   ├── components/
│   │   ├── FileUpload.tsx             # Componente de carga de archivos
│   │   ├── ImageViewer.tsx            # Visor de radiografías
│   │   ├── SpineDiagram.tsx           # Diagrama de columna vertebral
│   │   ├── MeasurementsTable.tsx      # Tabla de mediciones
│   │   └── HeatmapVisualization.tsx   # Visualización 3D con mapa de calor
│   └── services/
│       └── api.ts                      # Servicio de API para backend
└── styles/
    └── index.css                       # Estilos globales
```

## Conexión con el Backend

### Requisitos Previos

1. Tener el backend corriendo desde el repositorio principal
2. Docker y Docker Compose instalados (para el backend)

### Iniciar el Backend

```bash
# Clonar el repositorio backend
git clone https://github.com/oesquivel81/MAIA-SPINE-ANATOMIC_MANIFOLD_CNN_TDA.git
cd MAIA-SPINE-ANATOMIC_MANIFOLD_CNN_TDA

# Iniciar los servicios con Docker Compose
docker-compose up -d

# Verificar que el backend esté corriendo
curl http://localhost:8000/api/v1/health
```

El backend estará disponible en `http://localhost:8000`

### Configuración de la API

El frontend está configurado para conectarse al backend en `http://localhost:8000/api/v1`. Esta configuración se encuentra en `src/app/services/api.ts`:

```typescript
const API_BASE_URL = 'http://localhost:8000/api/v1';
```

Si necesitas cambiar la URL del backend, modifica esta variable.

## Endpoints Disponibles

El servicio de API (`src/app/services/api.ts`) proporciona los siguientes métodos:

### Archivos
- `uploadFile(file: File)`: Subir archivo al backend
- `getFileMetadata(fileId: string)`: Obtener metadata de un archivo

### Normalización
- `normalizeImage(file: File, profileSource?, compareFile?, compareProfileJson?)`: Normalizar imagen de radiografía
- `getProfileStatus(sampleSize?: number)`: Obtener estado de perfiles de normalización
- `bootstrapProfiles()`: Inicializar perfiles de normalización

### Salud
- `checkHealth()`: Verificar estado del backend

## Desarrollo

### Instalación de Dependencias

```bash
pnpm install
```

### Notas Importantes

1. **No ejecutar `vite build`**: Este es un proyecto de Figma Make, no una configuración estándar de Vite
2. **El servidor Vite ya está corriendo**: No es necesario iniciar el dev server manualmente
3. **Entrypoint automático**: El archivo `__figma__entrypoint__.ts` se genera automáticamente

## Uso de la Aplicación

1. **Cargar imagen**: 
   - Arrastra una radiografía al área de carga
   - O haz clic en "Seleccionar archivo"

2. **Analizar imagen**:
   - Una vez cargada la imagen, haz clic en "Analizar imagen"
   - El sistema enviará la imagen al backend para normalización

3. **Ver resultados**:
   - Usa las pestañas para cambiar entre vistas
   - Revisa las mediciones en la tabla
   - Explora la visualización 3D arrastrando el mouse

4. **Generar reporte**:
   - Haz clic en "Descargar reporte" para obtener un PDF (próximamente)

## Componentes Principales

### FileUpload
Componente de carga de archivos con soporte drag-and-drop.

### ImageViewer
Visor de imágenes con controles de zoom y rotación para radiografías médicas.

### SpineDiagram
Visualización SVG de la columna vertebral con resaltado de vértebras específicas.

### MeasurementsTable
Tabla de mediciones con indicadores de estado (normal, advertencia, crítico).

### HeatmapVisualization
Canvas interactivo que muestra un mapa de calor 3D de la columna vertebral.

## Datos de Ejemplo

La aplicación incluye datos de muestra para demostración:

- Mediciones de ángulos (Cobb, inclinación pélvica, lordosis, cifosis)
- Vértebras resaltadas (T8, T9, T10, L1)
- Escala de colores para intensidad del mapa de calor

## Arquitectura Backend

El backend utiliza:
- **FastAPI**: Framework web
- **MongoDB**: Almacenamiento de metadata
- **Redis**: Cache de perfiles
- **LocalStack S3**: Almacenamiento de archivos
- **Docker Compose**: Orquestación de servicios

Ver el repositorio backend para más detalles: https://github.com/oesquivel81/MAIA-SPINE-ANATOMIC_MANIFOLD_CNN_TDA.git

## Próximas Funcionalidades

- [ ] Generación de reportes PDF
- [ ] Comparación de imágenes antes/después
- [ ] Historial de análisis
- [ ] Exportación de mediciones a CSV
- [ ] Integración con sistema de perfiles personalizados

## Licencia

Ver el repositorio principal para información de licencia.
