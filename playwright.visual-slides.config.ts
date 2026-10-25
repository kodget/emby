import { defineConfig } from '@playwright/test';
import repairConfig from './playwright.repairs.config';

export default defineConfig({
  ...repairConfig,
  grep: /background upload preparation|visual slide preparation|standalone deck chat|extraction warning names/,
});
