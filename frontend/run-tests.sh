#!/bin/bash
# Run frontend tests in batches to avoid memory issues
# Individual test files pass, but running all 8 together causes OOM

set -e

echo "Running frontend tests in batches..."
echo ""

# Batch 1: Small tests
echo "Batch 1: Small component tests"
npm test src/test/loading.test.tsx src/test/i18n.test.ts src/test/backtest-tag.test.tsx

# Batch 2: Medium tests
echo ""
echo "Batch 2: Medium component tests"
npm test src/test/disclaimer-banner.test.tsx src/test/api-client.test.ts src/test/auth-context.test.tsx

# Batch 3: Large tests (run separately)
echo ""
echo "Batch 3: Hook tests"
npm test src/test/useQuery.test.ts

echo ""
echo "Batch 4: Filter tests"
npm test src/test/useFilters.test.ts

echo ""
echo "✅ All test batches completed successfully!"
