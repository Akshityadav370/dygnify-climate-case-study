import {
  BarController, BarElement, CategoryScale, Chart as ChartJS, Legend, LinearScale,
  LineController, LineElement, PointElement, Tooltip,
} from 'chart.js'

ChartJS.register(BarController, BarElement, LineController, LineElement, PointElement, CategoryScale, LinearScale, Tooltip, Legend)
