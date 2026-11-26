import type {Config} from 'tailwindcss';
export default {content:['./src/**/*.{ts,tsx}'],theme:{extend:{colors:{border:'hsl(var(--border))',primary:'hsl(var(--primary))',background:'hsl(var(--background))',foreground:'hsl(var(--foreground))'},borderRadius:{lg:'.65rem'}}},plugins:[]} satisfies Config;
