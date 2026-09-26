/**
 * Types mirroring the public API contract (backend/app/schemas.py).
 *
 * Money arrives as a decimal string, never a JS number - floats must not touch
 * prices. Format with Intl.NumberFormat at render time.
 */

export type Availability =
  | "IN_STOCK"
  | "LOW_STOCK"
  | "OUT_OF_STOCK"
  | "SOLD"
  | "HIDDEN";

export type ProductCondition =
  | "NEW"
  | "UNWORN"
  | "EXCELLENT"
  | "VERY_GOOD"
  | "GOOD";

export type SortOption =
  | "featured"
  | "newest"
  | "price_asc"
  | "price_desc"
  | "best_selling";

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface Brand {
  id: number;
  name: string;
  slug: string;
  description: string | null;
  logo_url: string | null;
}

export interface Category extends Omit<Brand, "logo_url"> {
  image_url: string | null;
}

export interface ProductImage {
  id: number;
  url: string;
  alt_text: string | null;
  sort_order: number;
  is_primary: boolean;
}

/** Server-calculated. The client renders these numbers and derives none of them. */
export interface Pricing {
  currency: string;
  price: string | null;
  compare_at_price: string | null;
  estimated_market_price: string | null;
  discount_amount: string;
  final_price: string | null;
  discount_percent: number | null;
  promotion_name: string | null;
  /** No selling price has been set; show an enquiry CTA, not a number. */
  price_on_request: boolean;
}

export interface ProductSummary {
  id: number;
  name: string;
  slug: string;
  short_description: string | null;
  brand: Brand | null;
  primary_image: ProductImage | null;
  pricing: Pricing;
  availability: Availability;
  featured: boolean;
  new_arrival: boolean;
  condition: ProductCondition | null;
  /** The watch alone on a transparent background, for the homepage wrist. */
  cutout_url: string | null;
}

export interface ProductSpecifications {
  reference_number?: string | null;
  sku?: string | null;
  condition?: ProductCondition | null;
  production_year?: number | null;
  movement?: string | null;
  case_material?: string | null;
  case_size?: string | null;
  dial?: string | null;
  crystal?: string | null;
  strap_material?: string | null;
  water_resistance?: string | null;
  included_items?: string | null;
  limited_edition?: string | null;
}

export interface ProductDetail extends ProductSummary {
  description: string | null;
  images: ProductImage[];
  categories: Category[];
  specifications: ProductSpecifications;
  warranty_information: string | null;
  shipping_information: string | null;
  stock_quantity: number;
  related: ProductSummary[];
}

export interface PostSummary {
  id: number;
  title: string;
  slug: string;
  excerpt: string | null;
  cover_image_url: string | null;
  category: string | null;
  author_name: string | null;
  featured: boolean;
  published_at: string | null;
}

export interface PostDetail extends PostSummary {
  content: string | null;
}

export interface Banner {
  id: number;
  title: string;
  description: string | null;
  image_url: string | null;
  cta_label: string | null;
  cta_url: string | null;
}

export type HomepageSectionType =
  | "HERO"
  | "FEATURED_PRODUCTS"
  | "NEW_ARRIVALS"
  | "CATEGORIES"
  | "BRAND_STORY"
  | "FEATURED_PRODUCT"
  | "EDITORIAL"
  | "OFFERS"
  | "JOURNAL"
  | "SOCIAL"
  | "NEWSLETTER";

export interface HomepageSection {
  section_type: HomepageSectionType;
  title: string | null;
  subtitle: string | null;
  body: string | null;
  image_url: string | null;
  cta_label: string | null;
  cta_url: string | null;
  sort_order: number;
}

export interface Homepage {
  sections: HomepageSection[];
  banners: Banner[];
  featured_products: ProductSummary[];
  new_arrivals: ProductSummary[];
  latest_posts: PostSummary[];
}

export interface SiteSettings {
  brand_name: string;
  owner_name: string | null;
  tagline: string | null;
  logo_url: string | null;
  favicon_url: string | null;
  contact_email: string | null;
  contact_phone: string | null;
  address: string | null;
  currency: string;
  shipping_information: string | null;
  return_policy: string | null;
  warranty_information: string | null;
  seo_title: string | null;
  seo_description: string | null;
}

export interface SocialLink {
  platform: string;
  label: string | null;
  url: string;
}

export interface CatalogQuery {
  q?: string;
  category?: string;
  brand?: string;
  min_price?: string;
  max_price?: string;
  in_stock?: boolean;
  movement?: string;
  featured?: boolean;
  new_arrival?: boolean;
  sort?: SortOption;
  page?: number;
  page_size?: number;
}

export interface InquiryInput {
  full_name: string;
  email: string;
  phone: string;
  product_id: number | null;
  message: string | null;
}
