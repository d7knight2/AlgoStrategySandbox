import {
  deploymentNotes,
  integrationSteps,
  researchSources,
  strategyCards,
} from '@/lib/research/lumibotAlpacaReport';

describe('lumibotAlpacaReport data', () => {
  it('has at least three strategy cards with unique ids', () => {
    expect(strategyCards.length).toBeGreaterThanOrEqual(3);

    const ids = strategyCards.map((card) => card.id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it('ensures each strategy has risk rules and summary text', () => {
    strategyCards.forEach((card) => {
      expect(card.riskRules.length).toBeGreaterThan(0);
      expect(card.summary.length).toBeGreaterThan(10);
      expect(card.lumibotSketch.length).toBeGreaterThan(10);
    });
  });

  it('contains an actionable integration roadmap and deployment notes', () => {
    expect(integrationSteps.length).toBeGreaterThanOrEqual(4);
    expect(deploymentNotes.length).toBeGreaterThanOrEqual(3);
  });

  it('keeps links to all research sources', () => {
    expect(researchSources).toEqual(
      expect.arrayContaining([
        expect.stringContaining('lumibot.lumiwealth.com'),
        expect.stringContaining('alpaca.markets'),
        expect.stringContaining('vercel.com/docs/cron-jobs'),
      ]),
    );
  });
});
