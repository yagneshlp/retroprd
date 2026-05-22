#!/usr/bin/env bash
# Creates a minimal test git repository for retroprd evals.
#
# The repo simulates a 5-commit SaaS app build: scaffold → auth → schema →
# bug fix → billing. It is self-contained and leaves no side effects beyond
# the target directory.
#
# Usage:
#   bash setup_test_repo.sh [target_dir]
#
# Arguments:
#   target_dir   Where to create the repo (default: /tmp/retroprd-eval-repo)
#
# The script is idempotent: running it again recreates the repo from scratch.

set -euo pipefail

REPO_DIR="${1:-/tmp/retroprd-eval-repo}"

echo "Creating test repo at $REPO_DIR..."

rm -rf "$REPO_DIR"
mkdir -p "$REPO_DIR"
cd "$REPO_DIR"

git init -q
git config user.email "builder@example.com"
git config user.name "Test Builder"

# ── Commit 1: scaffold ──────────────────────────────────────────────────────

mkdir -p src
cat > README.md <<'EOF'
# TaskFlow

A simple SaaS task management app for small teams.

## Setup

```
npm install
npm run dev
```
EOF

cat > package.json <<'EOF'
{
  "name": "taskflow",
  "version": "0.1.0",
  "scripts": {
    "dev": "next dev",
    "build": "next build"
  },
  "dependencies": {
    "next": "^14.0.0",
    "react": "^18.0.0"
  }
}
EOF

mkdir -p app
cat > app/page.tsx <<'EOF'
export default function Home() {
  return <main><h1>TaskFlow</h1></main>;
}
EOF

git add .
git commit -q -m "Initial commit: scaffold Next.js app"

# ── Commit 2: auth ──────────────────────────────────────────────────────────

cat > src/auth.ts <<'EOF'
import { createClient } from '@supabase/supabase-js';

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
);

export async function signIn(email: string, password: string) {
  return supabase.auth.signInWithPassword({ email, password });
}

export async function signOut() {
  return supabase.auth.signOut();
}

export async function getUser() {
  return supabase.auth.getUser();
}
EOF

cat > .env.example <<'EOF'
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key
EOF

git add .
git commit -q -m "Add user authentication with Supabase"

# ── Commit 3: schema ────────────────────────────────────────────────────────

mkdir -p supabase/migrations
cat > supabase/migrations/001_init.sql <<'EOF'
-- Users are managed by Supabase Auth; we extend with a profile table
create table profiles (
  id uuid references auth.users primary key,
  display_name text,
  created_at timestamptz default now()
);

create table tasks (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid references profiles(id) not null,
  title text not null,
  completed boolean default false,
  due_date date,
  created_at timestamptz default now()
);

-- RLS
alter table tasks enable row level security;
create policy "Users see own tasks" on tasks
  for all using (auth.uid() = owner_id);
EOF

git add .
git commit -q -m "Add database schema and RLS migrations"

# ── Commit 4: bug fix ───────────────────────────────────────────────────────

cat > src/auth.ts <<'EOF'
import { createClient } from '@supabase/supabase-js';

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
);

export async function signIn(email: string, password: string) {
  return supabase.auth.signInWithPassword({ email, password });
}

export async function signOut() {
  return supabase.auth.signOut();
}

export async function getUser() {
  // Fix: getSession() was returning stale token after expiry.
  // getUser() hits the server and always returns the current auth state.
  const { data: { user } } = await supabase.auth.getUser();
  return user;
}
EOF

git add .
git commit -q -m "Fix auth token expiry bug — use getUser() instead of getSession()"

# ── Commit 5: billing ───────────────────────────────────────────────────────

cat > src/billing.ts <<'EOF'
import Stripe from 'stripe';

const stripe = new Stripe(process.env.STRIPE_SECRET_KEY!);

export async function createCheckoutSession(userId: string, priceId: string) {
  return stripe.checkout.sessions.create({
    mode: 'subscription',
    line_items: [{ price: priceId, quantity: 1 }],
    success_url: `${process.env.NEXT_PUBLIC_APP_URL}/billing/success`,
    cancel_url: `${process.env.NEXT_PUBLIC_APP_URL}/billing/cancel`,
    metadata: { userId },
  });
}

export async function getSubscription(customerId: string) {
  const subs = await stripe.subscriptions.list({ customer: customerId });
  return subs.data[0] ?? null;
}
EOF

cat >> .env.example <<'EOF'
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
NEXT_PUBLIC_APP_URL=http://localhost:3000
EOF

git add .
git commit -q -m "Add billing with Stripe — monthly and annual subscription plans"

echo ""
echo "Done. Repository created at $REPO_DIR"
echo ""
git -C "$REPO_DIR" log --oneline
