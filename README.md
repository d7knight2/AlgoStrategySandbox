# AlgoStrategySandbox

A QuantConnect Integration Starter Site for building and managing stock portfolios using QuantConnect APIs. This web application helps you create both paper trading (simulated) and live portfolios with algorithmic trading strategies.

## Features

- 🚀 **Easy Setup** - Get started quickly with a modern Next.js application
- 📊 **Portfolio Management** - Create, view, and manage multiple portfolios
- 📈 **Paper Trading** - Test strategies with simulated portfolios
- 💰 **Live Trading** - Deploy strategies to real markets via QuantConnect
- 🔌 **QuantConnect API Integration** - Full integration with QuantConnect's powerful API
- 🤖 **Lumibot + Alpaca Research Report** - Strategy templates and deployment plan for paper trading
- 🎨 **Modern UI** - Clean, responsive interface built with React and TypeScript

## Prerequisites

- Node.js 18.x or higher
- npm or yarn
- A [QuantConnect account](https://www.quantconnect.com/) (free tier available)

## Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/d7knight2/AlgoStrategySandbox.git
cd AlgoStrategySandbox
```

### 2. Install dependencies

```bash
npm install
```

### 3. Configure QuantConnect API credentials

1. Sign up for a QuantConnect account at [https://www.quantconnect.com/](https://www.quantconnect.com/)
2. Get your API credentials from your QuantConnect dashboard:
   - User ID: Found in your account settings
   - API Token: Generate one in the API section

3. Create a `.env` file from the example:

```bash
cp .env.example .env
```

4. Edit `.env` and add your credentials:

```env
NEXT_PUBLIC_QUANTCONNECT_USER_ID=your_user_id_here
NEXT_PUBLIC_QUANTCONNECT_API_TOKEN=your_api_token_here
QUANTCONNECT_API_BASE_URL=https://www.quantconnect.com/api/v2
```

### 4. Run the development server

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser to see the application.

## Usage

### Creating a Portfolio

1. Navigate to the **Portfolios** page
2. Enter a name for your new portfolio
3. Click **Create Portfolio**
4. Your portfolio will be created as a QuantConnect project

### Managing Portfolios

- **View Details**: Click on a portfolio to see its details and performance
- **Delete**: Remove portfolios you no longer need
- **Track Performance**: Monitor holdings, P&L, and other metrics

### Paper vs. Live Trading

- **Paper Trading**: Simulated portfolios for testing strategies without risk
- **Live Trading**: Connect to real brokerages through QuantConnect for actual trading

### Iterating Strategies on Historical + Paper Data

If you want to improve a strategy in loops, use this cycle:

1. **Backtest on historical data** in QuantConnect (fast iteration on parameters and rules).
2. **Compare backtest runs** (Sharpe, drawdown, turnover, win/loss profile).
3. **Paper trade** the best candidates to validate fill quality and slippage.
4. **Promote to live only after paper validation**.

This repo exposes backtest helpers in `QuantConnectClient`:

- `runBacktest({ projectId, compileId, backtestName })`
- `listBacktests(projectId)`

The primary path is QuantConnect's API plus the app's client wrapper. Python trading-core stays paper-only (`TRADING_MODE=paper`).

### Lumibot + Alpaca Report

- Open `/report` to review the integration roadmap and strategy catalog.
- See `docs/lumibot-alpaca-vercel-report.md` for the full implementation report.
- Use starter strategy templates in `strategies/lumibot/` to begin paper trading experiments.
- Pi Telegram + paper-loop improvement plan: `docs/IMPROVEMENT_PLAN.md`.

### Pi MCP (Cursor)

This repo includes `.cursor/mcp.json` so Cursor can delegate strategy work to the [Pi MCP server](https://www.npmjs.com/package/pi-mcp-server).

1. Set `PI_MCP_API_KEY` in your Cursor MCP environment (or export it in your shell).
2. Reload Cursor so it picks up `.cursor/mcp.json`.
3. Ask the agent to use the `pi` MCP tools when iterating on files under `strategies/lumibot/`.

Sandbox mode is enabled with writes limited to `strategies/lumibot/` and `src/lib/research/`. For full sandbox support, install the optional dependency:

```bash
npm install @anthropic-ai/sandbox-runtime
```

### Alpaca MCP (Cursor)

The same `.cursor/mcp.json` also configures the official [Alpaca MCP server](https://github.com/alpacahq/alpaca-mcp-server) for paper-trading operations from Cursor.

1. Install [uv](https://docs.astral.sh/uv/getting-started/installation/) so `uvx` is available.
2. Set these in Cursor MCP environment (paper keys from the [Alpaca dashboard](https://app.alpaca.markets/)):
   - `ALPACA_API_KEY`
   - `ALPACA_SECRET_KEY`
3. Reload Cursor.

Paper trading is enforced via `ALPACA_PAPER_TRADE=true`. Tool access is limited to `account`, `trading`, `stock-data`, and `assets` for safer strategy validation workflows.

To switch to live trading later, change `ALPACA_PAPER_TRADE` to `false` and use live API keys only after your promotion gates pass.

## Project Structure

```
AlgoStrategySandbox/
├── .cursor/
│   └── mcp.json            # Pi + Alpaca MCP server config for Cursor
├── docs/                   # Research and implementation reports
├── strategies/             # Python strategy templates for Lumibot
├── src/
│   ├── pages/              # Next.js pages
│   │   ├── index.tsx       # Home page
│   │   ├── portfolios.tsx  # Portfolio management page
│   │   └── _app.tsx        # App wrapper
│   ├── lib/                # Library code
│   │   └── quantconnect.ts # QuantConnect API client
│   ├── components/         # React components (future)
│   └── styles/             # Global styles
│       └── globals.css
├── public/                 # Static assets
├── .env.example           # Environment variables template
├── next.config.js         # Next.js configuration
├── tsconfig.json          # TypeScript configuration
└── package.json           # Project dependencies
```

## QuantConnect API Integration

The application uses the QuantConnect API v2 for all operations. Key features include:

- **Project Management**: Create, read, update, and delete projects
- **Backtesting**: Run and analyze strategy backtests
- **Live Trading**: Deploy and monitor live algorithms
- **Data Access**: Access historical and real-time market data

### API Client

The `QuantConnectClient` class in `src/lib/quantconnect.ts` provides a typed interface for all API operations:

```typescript
import { createQuantConnectClient } from '@/lib/quantconnect';

const client = createQuantConnectClient();
const projects = await client.listProjects();
```

## Building for Production

```bash
npm run build
npm start
```

## Available Scripts

- `npm run dev` - Start development server
- `npm run build` - Build for production
- `npm start` - Start production server
- `npm run lint` - Run ESLint
- `npm test` - Run unit tests
- `npm run test:watch` - Run unit tests in watch mode
- `npm run test:coverage` - Generate test coverage report
- `npm run test:ui` - Run Playwright UI tests
- `npm run test:ui:headed` - Run UI tests with visible browser
- `npm run test:ui:report` - View Playwright test report

## Security Notes

⚠️ **Important**: Never commit your `.env` file or expose your API credentials publicly. The `.env` file is gitignored by default.

- Store API credentials securely
- Use environment variables for sensitive data
- Rotate API tokens regularly
- Consider using a secrets manager for production deployments

## Learn More

- [QuantConnect Documentation](https://www.quantconnect.com/docs)
- [QuantConnect API Reference](https://www.quantconnect.com/docs/v2)
- [Next.js Documentation](https://nextjs.org/docs)
- [React Documentation](https://react.dev)

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

### Testing Requirements

All pull requests must pass automated unit and UI tests before merging. See [TESTING.md](TESTING.md) for details on:
- Running tests locally
- Adding new tests
- Branch protection rules
- CI/CD workflows

## License

ISC

## Support

For issues related to:
- **This application**: Open an issue on GitHub
- **QuantConnect API**: Visit [QuantConnect's support](https://www.quantconnect.com/contact)

---

Built with ❤️ using Next.js and QuantConnect API