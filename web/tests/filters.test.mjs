import test from 'node:test';
import assert from 'node:assert/strict';
import { normalize, parseFilters, serializeFilters, matchesFilters, freshness, relativeTime, offerAvailability, offerStatus, orderDeals } from '../assets/app.mjs';
const taxonomy = { categories: [{ id: 'training' }, { id: 'software' }], topics: [{ id: 'blue-team-dfir' }, { id: 'ai-security' }] };
const deal = { vendor: 'TrainSec', product: 'EDR Internals', description: 'Detection engineering labs', coupon: 'BF2026', category: 'training', topics: ['blue-team-dfir'], last_offer_confirmed_at: '2026-11-03T10:00:00Z', first_seen_at: '2026-11-01T00:00:00Z' };
const filters = { query: '', vendor: '', category: '', topics: [] };
test('unicode and case normalization', () => { assert.equal(normalize('  SéCURITY  LABS '), 'security labs'); });
test('keyword words and coupon search match safely', () => {
 assert.equal(matchesFilters(deal, { ...filters, query: 'TRAINSEC edr' }), true);
 assert.equal(matchesFilters(deal, { ...filters, query: 'bf2026' }), true);
 assert.equal(matchesFilters(deal, { ...filters, query: '<script>' }), false);
});
test('groups AND but selected topics OR', () => {
 assert.equal(matchesFilters(deal, { ...filters, category: 'software' }), false);
 assert.equal(matchesFilters(deal, { ...filters, vendor: 'Another' }), false);
 assert.equal(matchesFilters(deal, { ...filters, topics: ['ai-security', 'blue-team-dfir'] }), true);
 assert.equal(matchesFilters(deal, { ...filters, topics: ['ai-security'] }), false);
});
test('filter URLs roundtrip and reject unknown choices', () => {
 const chosen = { query: 'EDR & cloud', category: 'training', vendor: 'TrainSec', topics: ['blue-team-dfir', 'ai-security'] };
 assert.deepEqual(parseFilters(serializeFilters(chosen), taxonomy, ['TrainSec']), { ...chosen, topics: ['ai-security', 'blue-team-dfir'] });
 assert.deepEqual(parseFilters('?category=bad&vendor=x&topic=x&topic=ai-security&topic=ai-security', taxonomy, ['TrainSec']), { ...filters, topics: ['ai-security'] });
});
test('stale, unavailable and future confirmations are not fresh', () => {
 const now = Date.parse('2026-11-03T13:01:00Z');
 assert.equal(freshness(deal.last_offer_confirmed_at, now), 'stale');
 assert.equal(freshness('invalid', now), 'unknown');
 assert.equal(freshness(null, now), 'unknown');
 assert.equal(freshness('2026-11-04T10:00:00Z', now), 'unknown');
 assert.equal(relativeTime(deal.last_offer_confirmed_at, now), 'Checked 3h ago');
});
test('expiry and upcoming offers are distinct from fetch failure', () => {
 const now = Date.parse('2026-11-03T12:00:00Z');
 assert.equal(offerAvailability({ ends_at: '2026-11-03T11:00:00Z' }, now), 'expired');
 assert.equal(offerAvailability({ starts_at: '2026-11-04T00:00:00Z' }, now), 'upcoming');
 assert.equal(offerAvailability({ ends_at: null, starts_at: null }, now), 'current');
 assert.equal(offerAvailability({ expiry_cutoff_at: '2026-12-02T12:00:00Z' }, Date.parse('2026-12-02T11:59:59Z')), 'current');
 assert.equal(offerAvailability({ expiry_cutoff_at: '2026-12-02T12:00:00Z' }, Date.parse('2026-12-02T12:00:00Z')), 'expired');
});
test('fresh cards precede stale cards, not merely newest collection', () => {
 const now = Date.parse('2026-11-03T12:00:00Z');
 const stale = { ...deal, product: 'Stale', first_seen_at: '2026-11-03T11:00:00Z', last_offer_confirmed_at: '2026-11-02T10:00:00Z' };
 assert.equal(orderDeals([stale, deal], now)[0].product, deal.product);
});

test('upcoming status stays visible when evidence is stale', () => {
 const now = Date.parse('2026-11-03T15:00:00Z');
 const future = { ...deal, starts_at: '2026-11-04T00:00:00Z' };
 assert.equal(offerStatus(future, now), 'Upcoming · Recheck pending');
 assert.equal(offerStatus({ ...future, last_offer_confirmed_at: '2026-11-03T14:00:00Z' }, now), 'Upcoming');
 assert.equal(offerAvailability({ expiry_label: 'November 2026 only' }, Date.parse('2026-12-02T00:00:00Z')), 'expired');
});
