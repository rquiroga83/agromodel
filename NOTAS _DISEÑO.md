Confirmado: UPRA no monitorea maíz ni cacao en Cundinamarca.

Los endpoints existen y responden con estructura válida, pero devuelven 0 features para el bbox de Cundinamarca.
Maíz: pese al nombre "nivel nacional", el monitoreo satelital UPRA solo cubre las zonas maiceras industriales (Tolima, Huila, Meta, Córdoba, Valle) — Cundinamarca no está.
Cacao: servicio explícitamente es "región de la Orinoquía" (Meta, Casanare, Guaviare) — no cubre Cundinamarca.
Cobertura real de L1 monitoreo UPRA para Cundinamarca:

Cultivo	Capas	Clase MODEL_CLASSES
Papa	7 (2021 s1 a 2024 s1)	Papa
Arroz	7 (2021 s1 a 2024 s1)	Otros_cultivos (colapsa, no está en top-12)
Implicación para el diseño de 3 niveles: solo Papa y Arroz tendrán hard labels con confianza=1.0 vía L1. Todos los demás cultivos del catálogo (Cafe, Maíz, Plátano, Mango, Frijol, Cacao, Arveja, Palma, Banano, Naranja, Cana_Panelera) dependen exclusivamente de L2 EVA municipal (confianza 0.3-0.7) para etiquetas positivas. Esto ya está correctamente implementado en procesamiento/04_construir_vista_minable.py::asignar_target() según la memoria de diseño.

Ya puedes proceder con uv run procesamiento/04_construir_vista_minable.py para regenerar la vista minable.

Monitor cerrado. Resumen final del estado de targets:

Fuente	Capas OK	Notas
EVA (csv)	2 datasets	MADR 2007-2018 + UPRA 2019-2024
Monitoreo UPRA	14 (papa×7, arroz×7)	Maíz/cacao UPRA no cubre Cundinamarca
SIPRA	15	plátano parcial en .part.json (reanudable)
MGN-DANE	117 municipios	endpoint ESRI Colombia Municipios_2024


Fuentes de Etiquetado para Cundinamarca: Análisis Comparativo
Hallazgos clave por fuente
Fuente	Resolución espacial	Cultivos	Tipo	Confiabilidad ML
UPRA Monitoreo	Polígonos campo	7-8 cultivos	Observacional satelital	Excelente
EVA	Municipal (~1000 km²)	211 cultivos	Auto-reporte MADR	Baja (sesgo reportador)
SIPRA	Variable	~65 capas	Prescriptivo	No es ground truth
DANE CNA 2014	GPS parcela	Integral	Censal observacional	Buena (pero 2014)
WorldCereal ESA	10 metros	Maíz, cereales	Satelital global	Buena (2021+)
IGAC/IDEAM	1:100.000	Cobertura general	Observacional	Máscara territorial
Diagnóstico por fuente
UPRA Monitoreo Satelital — La mejor fuente posible. Polígonos de campo delimitados con Sentinel-1/2 + ML, validados con precisión del productor y kappa. Limitación fatal para tu objetivo: solo cubre papa, maíz, arroz, cacao, plátano, caña panelera, pastos nacionalmente. En Cundinamarca solo papa y arroz tienen cobertura real (confirmado en sesión anterior).

EVA (211 cultivos) — La única fuente que cubre diversidad de cultivos. El problema: los datos son auto-reportados por extensionistas y agricultores, con >60% de imprecisión documentada en estudios. Útil para tendencias sectoriales, problemático como etiqueta de campo en ML.

SIPRA — Es prescriptivo ("qué podría crecer"), no descriptivo ("qué crece"). Investigación confirma la brecha: hay 3.3M ha aptas para aguacate Hass pero solo 0.75% cultivadas. El uso actual en el proyecto (solo para No_apto) es el correcto.

DANE CNA 2014 — Censo con coordenadas GPS de parcelas, la mayor cobertura censal de Colombia en 55 años. Problema: tiene 12 años de antigüedad. Podría servir como base histórica si consigues los microdatos desde microdatos.dane.gov.co.

WorldCereal ESA — Novedad importante. Mapas de cultivos a 10 metros con Sentinel-1/2, disponibles en Google Earth Engine desde 2021. Cubre maíz y cereales. Podría llenar el vacío de UPRA para maíz en Cundinamarca y mejorar la etiqueta de confianza para ese cultivo.

Conclusión para el diseño del proyecto
El cuello de botella no es el modelo, es la disponibilidad de ground truth a nivel de campo.

Para predecir más de 7-8 cultivos con alta confianza, las opciones reales son:

Opción A — Estrategia actual (L1/L2/L3), mejorada con WorldCereal:

L1: UPRA (papa, arroz) → confianza=1.0
L1b: WorldCereal maíz validado localmente → confianza=0.85
L2: EVA municipal (café, caña, frijol, arveja, mango, etc.) → confianza=0.3-0.5
L3: No_apto vía SIPRA+NDVI → confianza=0.4
Resultado: ~10-12 cultivos, mismo diseño actual pero con maíz mejorado
Opción B — UPRA inter-departamental (tu propuesta anterior):

L1: UPRA local (papa, arroz) + UPRA de departamentos compatibles (maíz del Tolima, cacao de Orinoquía) → confianza=0.7-0.9
EVA como feature auxiliar (rendimiento_tha, área_histórica)
Resultado: 5-7 clases de mayor calidad vs 14 clases con mayor ruido
Riesgo: Distribuciones bioclimáticas entre departamentos pueden no transferirse
Opción C — Microdatos DANE 2014 (requiere gestión):

Solicitar microdatos con coordenadas GPS al DANE
Integrar como L2 histórico para cultivos no cubiertos por UPRA/EVA
Resultado: Potencialmente 20+ cultivos con etiquetas de campo
Limitación: 12 años de antigüedad, rotaciones de cultivo desde entonces
Recomendación concreta
A corto plazo (sin cambiar la arquitectura actual): Integra WorldCereal para maíz. Es la ganancia de mayor calidad con menor esfuerzo — pasas de confianza_maíz=0.3 (EVA municipal) a confianza_maíz=0.85 (10m satelital). El dataset está en Google Earth Engine como ESA/WorldCereal/2021/MODELS/global_CroplandMaize_2021.

A mediano plazo: Si quieres más de 8-10 cultivos confiables, el único camino es EVA con las limitaciones actuales o gestionar los microdatos del CNA 2014. No existe otra fuente de campo para cultivos como arveja, frijol, o hortalizas en Cundinamarca.

Diseño actual (14 clases con L1/L2/L3) es defensible — simplemente refleja la realidad de que para la mayoría de cultivos en Cundinamarca no hay monitoreo satelital sistemático. La confianza como peso ya compensa la heterogeneidad de calidad entre fuentes.