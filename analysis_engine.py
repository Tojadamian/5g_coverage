import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


def generate_coverage_analytics(raw_signal_matrix):
    """
    Takes an array of signal levels (dBm) returned from the simulation
    and builds an academic-grade coverage evaluation report.
    """
    df = pd.DataFrame(raw_signal_matrix, columns=['RSRP_dBm'])

    # Calculate key descriptive engineering statistics
    mean_signal = df['RSRP_dBm'].mean()
    p5_outage = df['RSRP_dBm'].quantile(0.05)
    reliability_pct = (df['RSRP_dBm'] >= -115).mean() * 100

    print("\n================== LINK ANALYSIS REPORT ==================")
    print(f"Mean Received Signal (RSRP):      {mean_signal:.2f} dBm")
    print(f"5th Percentile (Cell Edge Limit): {p5_outage:.2f} dBm")
    print(f"Overall 5G Service Availability:  {reliability_pct:.1f}%")
    print("==========================================================")

    # Build the Cumulative Distribution Function (CDF) Plot
    sorted_data = np.sort(df['RSRP_dBm'])
    y_values = np.arange(1, len(sorted_data) + 1) / len(sorted_data)

    plt.figure(figsize=(8, 5))
    plt.plot(sorted_data, y_values, marker='.', linestyle='none', color='#1f77b4', label='Simulated Users')
    plt.axvline(x=-115, color='r', linestyle='--', label='5G Outage Threshold (-115 dBm)')

    plt.title("CDF of Received Signal Strength (5G-NTN LEO)")
    plt.xlabel("Received Power Level (RSRP, dBm)")
    plt.ylabel("Probability (Fraction of covered study area)")
    plt.grid(True, which="both", ls="--", alpha=0.5)
    plt.legend(loc="upper left")

    output_path = 'ntn_coverage_cdf.png'
    plt.savefig(output_path, dpi=300)
    print("[SYSTEM INFO] Generated performance visualization plot: 'ntn_coverage_cdf.png'")

    return {
        "mean_signal_dbm": mean_signal,
        "p5_outage_dbm": p5_outage,
        "availability_pct": reliability_pct,
        "output_path": output_path,
    }


if __name__ == "__main__":
    # Test execution block simulating 500 ground nodes calculating coverage matrix returns
    dummy_matrix = np.random.normal(loc=-98, scale=12, size=500)
    generate_coverage_analytics(dummy_matrix)
