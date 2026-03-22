# Layer Trend Graph Design

## Goal

Revise the summary-page layer trend graph so it uses the portrait page more effectively and separates X and Y deviation behavior.

## Approved Design

- Replace the current `x=layer, y=error` trend plot with a horizontal plot using `x=deviation (mm), y=layer`.
- Show X and Y deviations as two series on the same axes.
- Use `mean ± std` horizontal error bars for each layer.
- Slightly offset the X and Y series vertically to reduce overlap.
- Keep the panel on the summary page in the current middle-left location.
- Add a zero-reference line and threshold reference lines for readability.
- Remove radial RMSE and worst-axis-max series from this panel.

## Scope

- In scope: summary-page layer trend panel in `src/report_generator.py`.
- Out of scope: classic multi-page error-bar report, metrics table contents, heatmap panel, and pass/fail logic.

## Notes

- The metrics table can continue to include radial aggregate metrics; this change is only for the layer trend visualization.
- The plot should emphasize per-layer directional bias and spread, not worst-case outliers.
