# More examples

Worked bad/good contrasts moved out of `SKILL.md`, grouped by the section whose rule each one illustrates.

## Descriptive titles (BDD-like)

- [Example]
```
Bad:  "should AND fieldA IN with fieldB NOT IN when both provided"   (operator mechanics)
Bad:  "regression: PR #2034 last-spread-wins on flowCode"            (session/branch history)
Good: "should subtract excludeFlowCodes from the flowCode include set when both filters are provided"
```

## One test per distinct cause

- [Example]
```ts
// Bad - three tests, one per trigger, all asserting the same behavior:
it('should reset page to 1 when status filter changes', ...);
it('should reset page to 1 when search input changes', ...);
it('should reset page to 1 when sort order changes', ...);

// Good - one test of the underlying invariant:
it('should reset page to 1 on every refetch of the dataset', ...);
```

## Splitting & grouping by behavior

- [Example] One test = one behavior asserted:
```ts
// Bad - compound assertion, hides which half failed
it('should render entity tabs and active-tab table on cold mount', ...);
it('should filter the table by agreementIds (or skus for the product tab)', ...);
it('should re-derive per-tab badges and the brand-selector dropdown', ...);

// Good - one observable behavior per test
it('should render the entity tabs on cold mount', ...);
it('should render the active-tab table on cold mount', ...);
it('should filter the sales-agreement tab table by agreementIds', ...);
it('should filter the product tab table by skus', ...);
it('should re-derive per-tab badges from school-scoped summary calls', ...);
it('should re-derive the brand-selector dropdown options from school-scoped summary calls', ...);
```

- [Example] Group tests by intent with nested describe blocks:
```ts
// Bad - mixed
describe('contractValidation.getSchoolsAgreementsAndSkus', () => {
  it('returns agreements + SKUs for valid input', ...);
  it('throws BAD_REQUEST when no schools provided', ...);
  it('attaches SKU codes returned by getSKUs', ...);
  it('throws INTERNAL_SERVER_ERROR after retries', ...);
});

// Good - split
describe('contractValidation.getSchoolsAgreementsAndSkus', () => {
  describe('happy path', () => {
    it('returns agreements + SKUs for valid input', ...);
    it('attaches SKU codes returned by getSKUs', ...);
  });

  describe('failure scenarios', () => {
    it('throws BAD_REQUEST when no schools provided', ...);
    it('throws INTERNAL_SERVER_ERROR after retries', ...);
  });
});
```

## Determinism & flakes

- [Example] Order-independent assertion, when order is not part of the contract:
```ts
// Bad -- breaks if implementation reorders items:
expect(result).toEqual([
    { sku: 'CHILD-1', price: 100 },
    { sku: 'KIT-1', price: 300 },
]);

// Good -- asserts membership and count, order-independent:
expect(result).toHaveLength(2);
expect(result).toEqual(expect.arrayContaining([
    expect.objectContaining({ sku: 'CHILD-1', price: 100 }),
    expect.objectContaining({ sku: 'KIT-1', price: 300 }),
]));
```

## Mocking, fixtures & test data

- [Example] Reach every test state through the factory's overrides:
```ts
// Bad - fixture only supports the happy path; "expired" test has to dig into internals:
const baseAgreement = { signedAt: '2025-01-01', deadline: '2025-12-31' };

it('shows expired badge when past deadline', () => {
  const agreement = { ...baseAgreement, deadline: '2020-01-01' };
});

// Good - factory with overrides; every state is one named override away:
function createAgreement(overrides: Partial<Agreement> = {}): Agreement {
  return { signedAt: '2025-01-01', deadline: '2025-12-31', ...overrides };
}

it('shows expired badge when past deadline', () => {
  const agreement = createAgreement({ deadline: '2020-01-01' });
});
```

## Assert real behavior, not implementation

- [Example] Hand-coded regression baseline instead of `f(X) === f(X)`:
```ts
// Bad -- two identical requests, asserting equal proves nothing:
const [a, b] = await Promise.all([
  request(app).get('/v1/things?resolved=false'),
  request(app).get('/v1/things?resolved=false'),
]);
expect(a.body).toEqual(b.body);

// Good -- single request + explicit hand-coded shape:
const response = await request(app).get('/v1/things?resolved=false');
expect(response.body.data).toHaveLength(1);
expect(response.body.data[0].entity).toBe('order');
expect(response.body.pagination).toEqual({ page: 1, pageSize: 20, totalItems: 1, totalPages: 1 });
```
