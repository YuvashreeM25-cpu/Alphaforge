// var_engine.cpp — C++17 Monte-Carlo VaR core, exposed to Python via pybind11.
//
// Why C++ here (and not Python): the inner loop draws millions of correlated
// normal vectors and reduces them to a portfolio P&L distribution. That is a
// tight numeric loop where Python's per-iteration overhead dominates. In C++
// the same work is ~10-50x faster (see ../benchmark.py). Knowing WHEN to drop
// to a fast language is the judgment quant desks test for — that is the only
// reason C++ is in this project.
//
// Build:  see ../README in risk/ or run `pip install ./risk/cpp` (uses pybind11).

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <vector>
#include <random>
#include <algorithm>
#include <cmath>

namespace py = pybind11;

// L is the lower-triangular Cholesky factor (row-major, n x n).
// mu is the per-asset mean daily return. w is portfolio weights.
// Returns {VaR, CVaR} as positive loss fractions at `confidence`.
std::vector<double> mc_var(
    const std::vector<double>& mu,
    const std::vector<double>& L,   // n*n row-major lower triangular
    const std::vector<double>& w,
    int n_assets,
    long n_paths,
    int horizon_days,
    double confidence,
    unsigned int seed)
{
    std::mt19937_64 gen(seed);
    std::normal_distribution<double> norm(0.0, 1.0);

    std::vector<double> losses;
    losses.reserve(n_paths);

    std::vector<double> z(n_assets);
    std::vector<double> corr(n_assets);

    for (long p = 0; p < n_paths; ++p) {
        double cum = 0.0;
        for (int d = 0; d < horizon_days; ++d) {
            for (int i = 0; i < n_assets; ++i) z[i] = norm(gen);
            // corr = L * z  (lower triangular matrix-vector product)
            for (int i = 0; i < n_assets; ++i) {
                double acc = 0.0;
                for (int j = 0; j <= i; ++j) acc += L[i * n_assets + j] * z[j];
                corr[i] = mu[i] + acc;
            }
            double port = 0.0;
            for (int i = 0; i < n_assets; ++i) port += w[i] * corr[i];
            cum += port;
        }
        losses.push_back(-cum);
    }

    std::sort(losses.begin(), losses.end());
    long idx = static_cast<long>(confidence * (losses.size() - 1));
    double var = losses[idx];
    double tail_sum = 0.0; long tail_n = 0;
    for (long i = idx; i < (long)losses.size(); ++i) { tail_sum += losses[i]; ++tail_n; }
    double cvar = tail_n ? tail_sum / tail_n : var;
    return {var, cvar};
}

PYBIND11_MODULE(var_engine, m) {
    m.doc() = "C++ Monte-Carlo VaR core";
    m.def("mc_var", &mc_var,
          py::arg("mu"), py::arg("L"), py::arg("w"),
          py::arg("n_assets"), py::arg("n_paths"),
          py::arg("horizon_days"), py::arg("confidence"), py::arg("seed"),
          "Returns {VaR, CVaR} loss fractions.");
}
