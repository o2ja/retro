/** Admin API contracts (backend/app/schemas.py). Money is always a string. */

import type { Availability, Page, ProductCondition } from "./types";

export type { Page };

export type OrderStatus =
  | "PENDING_PAYMENT"
  | "PAYMENT_CONFIRMED"
  | "PROCESSING"
  | "SHIPPED"
  | "DELIVERED"
  | "CANCELLED"
  | "REFUNDED";

export type PaymentStatus =
  | "PENDING"
  | "AUTHORIZED"
  | "PAID"
  | "FAILED"
  | "CANCELLED"
  | "REFUNDED";

export type PostStatus = "DRAFT" | "PUBLISHED" | "ARCHIVED";

/**
 * Mirrors ORDER_STATUS_TRANSITIONS minus PAYMENT_CONFIRMED, which only a
 * recorded payment can set. The server refuses anything else anyway.
 */
export const ORDER_TRANSITIONS: Record<OrderStatus, OrderStatus[]> = {
  PENDING_PAYMENT: ["CANCELLED"],
  PAYMENT_CONFIRMED: ["DELIVERED", "PROCESSING", "CANCELLED", "REFUNDED"],
  PROCESSING: ["SHIPPED", "DELIVERED", "CANCELLED", "REFUNDED"],
  SHIPPED: ["DELIVERED", "REFUNDED"],
  DELIVERED: ["REFUNDED"],
  CANCELLED: [],
  REFUNDED: [],
};

export interface Brand {
  id: number;
  name: string;
  slug: string;
  description: string | null;
  logo_url: string | null;
  active: boolean;
  sort_order: number;
  product_count: number;
}

export interface Category {
  id: number;
  name: string;
  slug: string;
  description: string | null;
  image_url: string | null;
  active: boolean;
  sort_order: number;
  product_count: number;
}

export interface AdminProduct {
  id: number;
  name: string;
  slug: string;
  sku: string;
  brand: { id: number; name: string; slug: string } | null;
  categories: { id: number; name: string; slug: string }[];
  price: string | null;
  compare_at_price: string | null;
  estimated_market_price: string | null;
  currency: string;
  stock_quantity: number;
  low_stock_threshold: number;
  availability: Availability;
  active: boolean;
  featured: boolean;
  new_arrival: boolean;
  is_unique: boolean;
  primary_image: { id: number; url: string; alt_text: string | null } | null;
  updated_at: string;
  condition?: ProductCondition | null;
}

export interface OrderItem {
  id: number;
  product_id: number | null;
  product_name_snapshot: string;
  brand_name_snapshot: string | null;
  sku_snapshot: string;
  unit_price: string;
  quantity: number;
  discount_amount: string;
  line_total: string;
}

export interface Order {
  id: number;
  order_number: string;
  customer_id: number | null;
  shipping_name: string;
  shipping_email: string;
  total: string;
  currency: string;
  payment_status: PaymentStatus;
  order_status: OrderStatus;
  created_at: string;
}

export interface OrderDetail extends Order {
  subtotal: string;
  discount_total: string;
  shipping_total: string;
  promotion_code_snapshot: string | null;
  shipping_phone: string | null;
  shipping_address: string;
  shipping_city: string;
  shipping_country: string;
  shipping_postal_code: string | null;
  customer_note: string | null;
  items: OrderItem[];
  payments: {
    id: number;
    provider: string;
    amount: string;
    currency: string;
    status: PaymentStatus;
    failure_reason: string | null;
    created_at: string;
  }[];
  status_history: {
    from_status: OrderStatus | null;
    to_status: OrderStatus;
    note: string | null;
    created_at: string;
  }[];
}

export interface Customer {
  id: number;
  email: string;
  full_name: string | null;
  phone: string | null;
  is_active: boolean;
  last_order_at: string | null;
  created_at: string;
}

export interface CustomerDetail extends Customer {
  order_count: number;
  total_spent: string;
  orders: Order[];
}

export interface Promotion {
  id: number;
  name: string;
  code: string | null;
  description: string | null;
  discount_type: "PERCENTAGE" | "FIXED_AMOUNT";
  discount_value: string;
  starts_at: string | null;
  ends_at: string | null;
  minimum_order_value: string | null;
  usage_limit: number | null;
  usage_count: number;
  active: boolean;
  product_ids: number[];
  category_ids: number[];
}

export interface Post {
  id: number;
  title: string;
  slug: string;
  excerpt: string | null;
  content: string | null;
  cover_image_url: string | null;
  category: string | null;
  author_name: string | null;
  status: PostStatus;
  featured: boolean;
  published_at: string | null;
  updated_at: string;
}

export interface HomepageSection {
  id: number;
  section_type: string;
  title: string | null;
  subtitle: string | null;
  body: string | null;
  image_url: string | null;
  cta_label: string | null;
  cta_url: string | null;
  visible: boolean;
  sort_order: number;
  updated_at: string;
}

export interface SocialLink {
  id: number;
  platform: string;
  label: string | null;
  url: string;
  active: boolean;
  sort_order: number;
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

export interface SeriesPoint {
  date: string;
  value: string;
}

export interface LabelledValue {
  label: string;
  revenue: string | null;
  units: number | null;
}

export interface Dashboard {
  range: { start: string; end: string; days: number };
  kpis: {
    revenue: string;
    orders: number;
    average_order_value: string;
    new_customers: number;
    customers: number;
    products: number;
    low_stock: number;
    out_of_stock: number;
    pending_payments: number;
    pending_orders: number;
  };
  revenue_series: SeriesPoint[];
  orders_series: SeriesPoint[];
  customer_series: SeriesPoint[];
  sales_by_category: LabelledValue[];
  sales_by_brand: LabelledValue[];
  best_selling_products: LabelledValue[];
  recent_orders: Order[];
  recent_customers: Customer[];
  low_stock_products: AdminProduct[];
}

export type InquiryStatus = "NEW" | "CONTACTED" | "SOLD" | "CLOSED";

export type PaymentMethod = "cash" | "bank_transfer" | "card_in_store";

export const PAYMENT_LABELS: Record<PaymentMethod, string> = {
  cash: "Cash",
  bank_transfer: "Bank transfer",
  card_in_store: "Card in store",
};

export interface Inquiry {
  id: number;
  product_id: number | null;
  product_name_snapshot: string | null;
  full_name: string;
  email: string;
  phone: string;
  message: string | null;
  status: InquiryStatus;
  order_number: string | null;
  created_at: string;
}
