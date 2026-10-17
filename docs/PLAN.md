# Dindo: plan del proyecto

**Concurso:** AMD Developer Hackathon: ACT III (lablab.ai), participación online.
**Track:** 2, Health and Wellbeing.
**Equipo:** 0605 (José Deybbie Claure Menacho, solo).
**Entrega:** domingo 18 de octubre de 2026, 06:00 hora de Bolivia (UTC-4). Meta interna: entregar el sábado 17 a la noche.

---

## 1. El problema

En 2022 a José lo atropelló un vehículo. Lo que siguió fue un calvario administrativo, además del físico:

- Recetas a mano, órdenes de internación, estudios, informes y citas en varias clínicas.
- Medicamentos con horarios que nadie recordaba: cuándo empezó cada uno, a qué hora tocaba, cuándo terminaba.
- Días de 4.000 Bs de gasto sin saber en qué, lo que generaba peleas en la familia.
- Facturas que había que presentar al seguro. El seguro (Alianza Vida) cubría hasta 12.000 Bs y se recuperaron solo unos 10.000.
- Números de emergencia, médicos y especialistas que no aparecían cuando hacían falta.
- Traslados en ambulancia y documentos del juicio por el accidente.

Las clínicas y los médicos tienen sistemas. **El paciente y su familia tienen una bolsa de papeles.** Lo mismo pasa con una cirugía, un familiar mayor o una mascota enferma.

## 2. La solución

**Dindo** es un gestor de casos de salud con IA. Le sacás foto a cualquier papel y la IA lo lee, lo organiza y **audita el caso**: detecta errores que hacen perder plata o que pueden ser peligrosos.

### Usuarios
- **Cada caso tiene miembros:** el paciente, la pareja, los padres, quien cuide.
- Cada gasto registra **quién lo pagó y quién lo cargó**.
- Puede haber varios casos, de personas o de mascotas (por ejemplo "Accidente de José" y "Perro Max").

### Plataforma
- Web pensada primero para el celular (para sacar fotos), adaptada también a PC.
- Instalable en la pantalla de inicio del celular, sin tiendas de apps.
- Idiomas: **español, inglés e italiano**, en las pantallas y en las respuestas de la IA.

## 3. Alcance

### Entra en la demo
| Código | Función |
|---|---|
| A1 | Foto o PDF → la IA clasifica y extrae: receta, factura, orden, informe, estudio, imagen médica, documento legal |
| A2 | Plan de medicación con horarios, alarmas y "día X de Y" |
| A3 | Gastos por categoría y por día, quién pagó, preguntas a la IA en lenguaje natural |
| A4 | Bóveda de documentos (incluye radiografías y tomografías) y compartir por WhatsApp o correo |
| A5 | Varios casos (persona o mascota) con miembros |
| A6 | La IA pregunta cuando duda y nunca inventa |
| A7 | 3 idiomas |
| A8 | Panel "Bajo el capó": cada llamada a AMD en vivo (modelo, tiempo, tokens) |
| B1 | Seguro: cobertura usada y restante, estado de cada factura, plazos, paquete de reclamo |
| B2 | Calendario de citas, estudios y audiencias |
| B3 | Línea de tiempo única del caso: médico y legal |
| B4 | Agenda de contactos por rol, llenada sola desde los documentos, y botón SOS |
| B5 | Carga rápida por texto: "pagué 150 al taxi para ir a fisio" |
| L1 | Documentos del juicio: audiencias, plazos, contactos legales, paquete de pruebas con el total de gastos documentados |

### Auditoría del caso (la IA trabajando)
Revisiones que hace Dindo sobre cada documento y entre documentos:
- **Fechas incoherentes:** una factura fechada antes del servicio que cobra.
- **Factura mal emitida:** no está a nombre del seguro o le falta el NIT.
- **Aritmética:** subtotales, descuentos y total.
- **Inconsistencias entre documentos:** lado del cuerpo (izquierda o derecha), nombre del paciente, fechas.
- **Pendientes:** estudios pedidos que todavía no tienen resultado.
- **Cruces:** asistencia firmada contra sesiones facturadas.
- **Plazos:** reembolsos por vencer, cobertura por agotarse, audiencias próximas.

### No entra
Carga por audio, bot de WhatsApp, pedir ambulancia o transporte, envío automático al seguro.

## 4. Reglas de seguridad (exigidas por el Track 2)

- **No diagnostica ni recomienda tratamientos.** Organiza, explica lo que ya indicó el médico y avisa.
- **No interpreta imágenes médicas.** Radiografías y tomografías se archivan, no se analizan.
- **No da consejo legal.** Organiza documentos y plazos del juicio.
- **La incertidumbre siempre se ve:** cada dato extraído lleva su nivel de confianza, y si la IA duda, pregunta.
- **Las alertas de riesgo** (como el lado equivocado en una orden) se presentan como "confirmalo con tu médico", nunca como una conclusión.
- **Datos sensibles:** modelos abiertos en infraestructura de AMD. Las claves nunca van al código ni al repositorio.

## 5. Tecnología

| Pieza | Elección |
|---|---|
| Pantallas | HTML, CSS y JavaScript, basadas en la maqueta, instalables como app web |
| Servidor | Python con FastAPI |
| Base de datos | SQLite y archivos en carpeta |
| IA | AMD Token Factory: Gemma 4 (lee imágenes) y DeepSeek (razona y responde). Modelos por confirmar al ver el catálogo. |
| Usuarios | Correo y contraseña, invitación a un caso con código |
| Publicación | Docker, hosting gratuito, repositorio público en GitHub con licencia MIT |

```
 Celular ──foto──▶  Servidor Dindo  ──▶  AMD Token Factory
                                           ├─ Gemma 4: lee la foto
                                           └─ DeepSeek: organiza, audita, responde
 Celular ◀── plan, gastos, alertas ────────┘
```

AMD confirmó en Discord que usar Token Factory cumple el requisito de "uso significativo de AMD". El código tiene que mostrar claramente las llamadas a los servidores de AMD. Si usar Gemma vía Token Factory califica para el premio de Google, competimos también por ese.

## 6. Datos de la demo

- **Documentos reales del accidente de José** (autorizado por él): `E:\FAMILY DOCUMENTS\ESTADO DE SALUD JOSE CLAURE`. Facturas de Rehalife y Médicos Cristianos Solidarios, informes, recetas y órdenes de Foianini, referencia al cirujano vascular y tomografía de rodilla.
- **Hallazgos reales para mostrar:**
  - La factura de Rehalife N.º 001648 está fechada el 09/01/2022 y cobra sesiones del 02 al 27/12/2022.
  - La solicitud de tomografía de Foianini dice "rodilla derecha"; el accidente fue en la izquierda (confirmado por José).
  - Contactos de médicos escondidos en sellos y notas a mano.
  - Resonancia, ecodoppler y tomografía como estudios pedidos.
- **Documentos del juicio:** pendiente de conseguir.
- **Caso de la mascota:** 2 o 3 recetas de veterinario, por definir.

## 7. Cronograma

| Cuándo | Qué |
|---|---|
| Miércoles 14 (hasta las 4 AM) | Plan, estructura, base de datos y pantallas con datos de ejemplo |
| Jueves 15 | IA: lectura de documentos, medicación, gastos |
| Viernes 16 | Auditoría, seguro, calendario, línea de tiempo, contactos, juicio, compartir, idiomas, usuarios, panel AMD |
| Sábado 17 | Pulido, publicación, README, video, slides, **entrega** |

## 8. Entregables (reglas de lablab)

- Título, descripción corta y larga, track y etiquetas de tecnología.
- Imagen de portada.
- Video de demostración.
- Presentación en slides.
- Repositorio público en GitHub con licencia MIT.
- Aplicación publicada con su URL.

## 9. Pendientes

- [ ] Clave de Token Factory (se pidió a @Maharshi en Discord).
- [ ] Ver el catálogo de modelos: confirmar Gemma 4 (visión), DeepSeek y los límites de uso.
- [ ] Cuenta de GitHub.
- [ ] Documentos del juicio.
- [ ] Recetas de la mascota.
- [ ] ¿Renombrar el equipo "0605" a "Dindo"?
- [ ] ¿Gemma vía Token Factory califica para el premio de Google?
