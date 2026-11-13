// Charging is energy that does not burn fuel, so it always gets green and no
// other bar does. Everything else walks through the remaining palette.
function createExpenseCategoryChart(element, categoryData, currency, chargingLabel) {
    const labels = Object.keys(categoryData);
    const GREEN = 'rgba(34, 197, 94, 0.8)';
    const palette = [
        'rgba(239, 68, 68, 0.8)', 'rgba(245, 158, 11, 0.8)',
        'rgba(14, 165, 233, 0.8)', 'rgba(168, 85, 247, 0.8)',
        'rgba(236, 72, 153, 0.8)', 'rgba(20, 184, 166, 0.8)',
        'rgba(249, 115, 22, 0.8)', 'rgba(99, 102, 241, 0.8)',
        'rgba(107, 114, 128, 0.8)', 'rgba(132, 204, 22, 0.8)'
    ];
    let next = 0;
    const colors = labels.map(l => l === chargingLabel ? GREEN : palette[next++ % palette.length]);
    return new Chart(element.getContext('2d'), {
            type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                data: labels.map(l => categoryData[l]),
                backgroundColor: colors,
                borderRadius: 4
            }]
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: (context) => context.formattedValue + ' ' + currency
                    }
                }
            },
            scales: {
                y: {
                    // Every bar keeps its name; Chart.js would otherwise hide
                    // every other label when the card is short.
                    ticks: { autoSkip: false }
                },
                x: {
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: currency
                    }
                }
            }
        }
    });
}
