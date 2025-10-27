import polars as pl

# Load summary
df = pl.read_parquet("data/03_intermediate/iv_fits/fit_summary.parquet")

# Find segments with poor fits (R² < 0.95)
poor_fits = df.filter(pl.col("r_squared") < 0.95)

# Compare polynomial orders
df.group_by("order").agg([
    pl.col("r_squared").mean().alias("mean_r2"),
    pl.col("rmse").mean().alias("mean_rmse")
])

# Get best order for each segment
best_fits = df.sort("r_squared", descending=True).group_by("run_id").first()

print(best_fits)