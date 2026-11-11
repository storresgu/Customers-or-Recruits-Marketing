from pathlib import Path
import json,sys
results=Path(sys.argv[1]);target=Path(sys.argv[2]);target.parent.mkdir(parents=True,exist_ok=True)
a=json.loads((results/'audit.json').read_text());sc=json.loads((results/'scenario_summary.json').read_text())
def n(x,d=2): return 'NA' if x is None else f'{x:.{d}f}'
lines=['# Article 25 — M4: informe del piloto y registro de decisiones v0.1','',
'Fecha: 6 de octubre de 2026. Modelo: **0.3.0-m3**. Especificación: **0.1**.',
'', '**El piloto concluyó: 40 pares y 80 trayectorias de rama, con 500 personas y 120 meses por trayectoria.** Se mantuvieron el código y el registro de semillas preparados en M3. Las 204 pruebas del modelo aprobaron nuevamente antes de ejecutar el piloto.',
'', '## 1. Diseño ejecutado','',
'Se cruzaron dos probabilidades de captación minorista (0,03 y 0,12) con dos probabilidades de recompra (0,30 y 0,80), con diez pares independientes por combinación. Cada par parte de la misma población, red e historia hasta el mes 60. El control conserva el reclutamiento; la otra rama lo interrumpe desde el mes 61. Hay diez distribuidores iniciales. Los demás parámetros son los del baseline registrado.',
'', f'La ejecución y exportación tardaron **{a["runtime_seconds"]/60:.2f} minutos** en este entorno. Los resultados brutos ocupan {a["raw_bytes"]/1024**3:.2f} GiB antes de comprimir. Este tiempo describe esta ejecución, no un rendimiento garantizado para el experimento principal.',
'', '## 2. Resultado principal del piloto','',
'La tabla usa el volumen externo acumulado en los meses 109–120. Las medias se calculan sobre diez réplicas. La diferencia es **shock menos control**. Los intervalos exploratorios del efecto medio se obtienen con 20.000 remuestreos de pares completos por escenario; con diez pares, su precisión sigue siendo limitada.',
'', '| Captación | Recompra | Control: media de unidades | Shock: media de unidades | Diferencia media | IC bootstrap 95% de la media | Controles <12 unidades | Razones indefinidas |',
'|---:|---:|---:|---:|---:|---:|---:|---:|']
for r in sc:
 lines.append(f'| {r["p_retail"]:.2f} | {r["p_repurchase"]:.2f} | {n(r["control_mean_late_external"])} | {n(r["shock_mean_late_external"])} | {n(r["mean_paired_difference"])} | [{n(r["mean_difference_bootstrap_ci025"])}, {n(r["mean_difference_bootstrap_ci975"])}] | {r["low_control_pairs"]}/10 | {r["undefined_resilience_pairs"]}/10 |')
lines += ['', 'En estas réplicas, el cociente entre el volumen medio del shock y el volumen medio del control fue aproximadamente 42–48% con captación baja y 75% con captación alta. Ese cociente de medias es distinto de la mediana de las razones individuales. La mayor recompra elevó el volumen absoluto, pero no eliminó la reducción asociada al shock.', '', 'Un denominador de control cero deja la razón indefinida, incluso cuando ambas ramas venden cero. Los volúmenes y las diferencias permanecen disponibles. La comparación principal conserva todos los pares y evita seleccionar únicamente las redes supervivientes.',
'', '## 3. Extinción e ingresos','',
'Extinción significa ausencia de distribuidores al cierre de algún mes hasta el 120. Con el estado inactivo absorbente del modelo, una red sin distribuidores no vuelve a activarse. La proporción de pérdidas se calcula para todos los participantes históricos de cada ejecución, incluidos quienes abandonaron, y luego se promedian las diez proporciones con igual peso por ejecución.',
'', '| Captación / recompra | Extinciones control | Extinciones shock | Pérdidas históricas: media control | Pérdidas históricas: media shock | Distribuidores finales: media control / shock |',
'|---|---:|---:|---:|---:|---:|']
for r in sc:
 lines.append(f'| {r["p_retail"]:.2f} / {r["p_repurchase"]:.2f} | {r["control_extinctions"]}/10 | {r["shock_extinctions"]}/10 | {100*r["control_mean_all_ever_loss_share"]:.1f}% | {100*r["shock_mean_all_ever_loss_share"]:.1f}% | {n(r["control_mean_final_D"])} / {n(r["shock_mean_final_D"])} |')
lines += ['', 'Los resultados de ingresos están en unidades monetarias normalizadas. No son estimaciones de empresas reales. Los CSV conservan medianas, cuantiles, Gini bruto, cohortes históricas y cohortes activas al cierre; no se calcula un Gini convencional sobre ingresos netos negativos.',
'', '## 4. Oportunidades locales y esfuerzo','',
'Para detectar agotamiento de oportunidades se registran las fracciones de contactos disponibles que no se usan en la ventana tardía y el número de vecinos elegibles al cierre. Los huecos de contacto pueden deberse a elegibilidad, solapamiento entre canales y orden de contacto; no prueban por sí solos saturación de todo el mercado.',
'', '| Captación / recompra | Cupos de reclutamiento sin usar: control | Cupos sin usar: shock | Vecinos elegibles por distribuidor activo: control | Vecinos elegibles: shock |',
'|---|---:|---:|---:|---:|']
for r in sc:
 def pct(x): return 'NA' if x is None else f'{100*x:.1f}%'
 lines.append(f'| {r["p_retail"]:.2f} / {r["p_repurchase"]:.2f} | {pct(r["control_mean_late_unused_recruitment_slot_share"])} | {pct(r["shock_mean_late_unused_recruitment_slot_share"])} | {n(r["control_mean_active_mean_eligible_recruitment_neighbors"])} | {n(r["shock_mean_active_mean_eligible_recruitment_neighbors"])} |')
lines += ['', 'Las medias de disponibilidad excluyen ejecuciones sin distribuidores activos cuando el denominador no existe. Por eso se interpretan junto con la tabla de extinción, no como un promedio sobre todas las personas. Los denominadores y valores faltantes por ejecución están en `run_diagnostics.csv`.',
'', '## 5. Auditoría y trazabilidad','',
 f'- {a["completed_pairs"]} pares completos, {a["completed_branches"]} ramas, {a["monthly_rows"]:,} registros mensuales y {a["participant_rows"]:,} filas de participantes por rama.',
 f'- {a["paired_effect_rows"]} efectos pareados: 40 pares × 3 ventanas × 3 resultados.',
 f'- Integridad comprobada de {a["files_hash_verified"]:,} archivos mediante las huellas del manifiesto.',
 '- Semillas y parámetros idénticos al registro de M3; las diferencias previas al shock son cero cuando están definidas.',
 '- Conservación de las 500 personas en todos los meses y cero incorporaciones tratadas desde el mes 61.',
 f'- Los ingresos netos acumulados por persona reconcilian con los totales mensuales; discrepancia máxima por redondeo: {a["max_cumulative_vs_monthly_cash_error"]:.3g}.',
 '- Estados, checkpoints, transacciones, eventos y registros financieros completos incluidos en cuatro archivos de trazas.',
 '', 'Huella del código del modelo:', '', f'`{a["code_hash"]}`',
 '', '## 6. Registro de decisiones después del piloto','',
 '1. **Cerrar M4 como ejecutado y auditado.** No se detectaron fallos de conservación, interrupción, identidad de semillas o conciliación de caja en esta ejecución.',
 '2. **Mantener los parámetros originales.** Los casos de bajo volumen, extinción o pérdidas se conservan como resultados de las reglas exploratorias. No se alteran para obtener trayectorias favorables.',
 '3. **Usar diferencias pareadas como resultado principal.** Las razones de resiliencia quedan como resultado complementario con su denominador, motivo de ausencia y bandera de bajo volumen.',
 '4. **Conservar el análisis de todos los participantes.** Presentar por separado los resultados de quienes siguen activos para que la selección por supervivencia sea visible.',
 '5. **No congelar todavía el experimento principal.** Diez pares por condición sirven para depuración y exploración, pero no sustituyen las réplicas ni la precisión previstas para M5. El cambio de N=500 a N=2.000 también puede modificar la saturación del mercado.',
 '6. **Próxima actividad: revisar y fijar el protocolo de M5.** La propuesta de la especificación cruza captación, recompra, esfuerzo de reclutamiento y abandono basal (16 escenarios). Cien pares por escenario equivalen a 1.600 pares o 3.200 ramas. Antes de esa ejecución hay que fijar el criterio de precisión, el tratamiento de casos de bajo volumen y las variantes de robustez, además de comprobar tiempo y almacenamiento con N=2.000.',
 '', 'Esta entrega no ejecuta M5, sensibilidad ni robustez estructural. Las diferencias observadas son resultados del modelo exploratorio y no evidencia causal sobre una organización real ni validación empírica de las reglas.',
 '', '## 7. Archivos y reproducción','',
 '- `Article_25_M4_Analisis_y_codigo_v0.1.zip`: código original M3, scripts de auditoría/análisis, tablas, figura, registro de semillas y metadatos de ejecución.',
 '- Cuatro archivos `Article_25_M4_Trazas_<escenario>_v0.1.zip`: diez pares completos por combinación.',
 '- `Article_25_M4_Informe_piloto_v0.1.md`: este informe.',
 '', 'Extraer los cinco ZIP en un mismo directorio reconstruye `Article_25_M4/`. El README contiene los comandos para repetir el piloto y el análisis. La figura describe medias y rangos intercuartílicos de las diez réplicas; sus bandas no son intervalos de confianza.',
 '', 'Entorno del modelo y análisis: CPython 3.12.14, NumPy 2.3.5, NetworkX 3.7, pytest 9.1.1. Se conserva el archivo de versiones probado y el entorno de Matplotlib usado únicamente para la figura.', '']
target.write_text('\n'.join(lines))
print(target)
