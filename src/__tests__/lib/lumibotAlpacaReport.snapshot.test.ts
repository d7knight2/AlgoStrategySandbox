import { strategyCards } from '@/lib/research/lumibotAlpacaReport';

describe('lumibotAlpacaReport snapshots', () => {
  it('matches the strategy catalog metadata snapshot', () => {
    const catalog = strategyCards.map(({ id, name, pythonFile, riskRules }) => ({
      id,
      name,
      pythonFile,
      riskRuleCount: riskRules.length,
    }));

    expect(catalog).toMatchSnapshot();
  });
});
