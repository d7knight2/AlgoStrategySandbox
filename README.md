# AlgoStrategySandbox

A QuantConnect Integration Starter Site for building and managing stock portfolios using QuantConnect APIs. This web application helps you create both paper trading (simulated) and live portfolios with algorithmic trading strategies.

## Features

- 🚀 **Easy Setup** - Get started quickly with a modern Next.js application
- 📊 **Portfolio Management** - Create, view, and manage multiple portfolios
- 📈 **Paper Trading** - Test strategies with simulated portfolios
- 💰 **Live Trading** - Deploy strategies to real markets via QuantConnect
- 🔌 **QuantConnect API Integration** - Full integration with QuantConnect's powerful API
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

## Project Structure

```
AlgoStrategySandbox/
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

## License

ISC

## Support

For issues related to:
- **This application**: Open an issue on GitHub
- **QuantConnect API**: Visit [QuantConnect's support](https://www.quantconnect.com/contact)

---

Built with ❤️ using Next.js and QuantConnect API