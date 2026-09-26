/**
 * Admin API client.
 *
 * Separate from `lib/api.ts` on purpose: every call here carries the session
 * cookie and every call there does not. Admin requests are never cached.
 */

import { ApiError } from "./api";
import type {
  AdminProduct,
  Brand,
  Category,
  Customer,
  CustomerDetail,
  Dashboard,
  HomepageSection,
  Inquiry,
  InquiryStatus,
  Order,
  PaymentMethod,
  OrderDetail,
  Page,
  Post,
  Promotion,
  SiteSettings,
  SocialLink,
} from "./admin-types";
import { getApiBaseUrl } from "./api";

type Method = "GET" | "POST" | "PATCH" | "PUT" | "DELETE";

export async function adminRequest<T>(
  path: string,
  { method = "GET", body }: { method?: Method; body?: unknown } = {},
): Promise<T> {
  const baseUrl = getApiBaseUrl();
  const response = await fetch(`${baseUrl}${path}`, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
    credentials: "include",
    cache: "no-store",
  });

  if (!response.ok) {
    let code = "http_error";
    let message = `Request failed (${response.status})`;
    try {
      const payload = await response.json();
      code = payload?.error?.code ?? code;
      message = payload?.error?.message ?? message;
      // Surface the first field error rather than a bare "invalid request".
      const detail = payload?.error?.details?.[0];
      if (detail) message = `${detail.field}: ${detail.message}`;
    } catch {
      // Non-JSON body; keep the generic message.
    }
    throw new ApiError(response.status, code, message);
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

const qs = (params: Record<string, unknown>) => {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") {
      search.set(key, String(value));
    }
  }
  return search.toString() ? `?${search}` : "";
};

/* Auth */
export const adminLogin = (email: string, password: string) =>
  adminRequest<{ id: number; email: string; full_name: string | null }>(
    "/api/admin/login",
    { method: "POST", body: { email, password } },
  );
export const adminLogout = () =>
  adminRequest<{ message: string }>("/api/admin/logout", { method: "POST" });
export const adminMe = () =>
  adminRequest<{ id: number; email: string; full_name: string | null }>(
    "/api/admin/me",
  );

/* Dashboard */
export const getDashboard = (params: Record<string, unknown>) =>
  adminRequest<Dashboard>(`/api/admin/dashboard${qs(params)}`);

/* Products & inventory */
export const listProducts = (params: Record<string, unknown>) =>
  adminRequest<Page<AdminProduct>>(`/api/admin/products${qs(params)}`);
export const getProduct = (id: number) =>
  adminRequest<AdminProduct>(`/api/admin/products/${id}`);
export const createProduct = (body: unknown) =>
  adminRequest<AdminProduct>("/api/admin/products", { method: "POST", body });
export const updateProduct = (id: number, body: unknown) =>
  adminRequest<AdminProduct>(`/api/admin/products/${id}`, { method: "PATCH", body });
export const deleteProduct = (id: number) =>
  adminRequest<{ message: string }>(`/api/admin/products/${id}`, { method: "DELETE" });
export const setInventory = (id: number, body: unknown) =>
  adminRequest<unknown>(`/api/admin/products/${id}/inventory`, { method: "PUT", body });
export const addProductImage = (id: number, body: unknown) =>
  adminRequest<unknown>(`/api/admin/products/${id}/images`, { method: "POST", body });
export const lowStock = () =>
  adminRequest<AdminProduct[]>("/api/admin/inventory/low-stock");

/* Brands & categories */
export const listBrands = () => adminRequest<Brand[]>("/api/admin/brands");
export const createBrand = (body: unknown) =>
  adminRequest<Brand>("/api/admin/brands", { method: "POST", body });
export const updateBrand = (id: number, body: unknown) =>
  adminRequest<Brand>(`/api/admin/brands/${id}`, { method: "PATCH", body });
export const deleteBrand = (id: number) =>
  adminRequest<{ message: string }>(`/api/admin/brands/${id}`, { method: "DELETE" });

export const listCategories = () => adminRequest<Category[]>("/api/admin/categories");
export const createCategory = (body: unknown) =>
  adminRequest<Category>("/api/admin/categories", { method: "POST", body });
export const updateCategory = (id: number, body: unknown) =>
  adminRequest<Category>(`/api/admin/categories/${id}`, { method: "PATCH", body });
export const deleteCategory = (id: number) =>
  adminRequest<{ message: string }>(`/api/admin/categories/${id}`, { method: "DELETE" });

/* Orders & customers */
export const listOrders = (params: Record<string, unknown>) =>
  adminRequest<Page<Order>>(`/api/admin/orders${qs(params)}`);
export const getOrder = (orderNumber: string) =>
  adminRequest<OrderDetail>(`/api/admin/orders/${orderNumber}`);
export const setOrderStatus = (orderNumber: string, status: string, note?: string) =>
  adminRequest<OrderDetail>(`/api/admin/orders/${orderNumber}/status`, {
    method: "PATCH",
    body: { order_status: status, note: note || null },
  });
export const refundOrder = (orderNumber: string, reason?: string) =>
  adminRequest<OrderDetail>(`/api/admin/orders/${orderNumber}/refund`, {
    method: "POST",
    body: { reason: reason || null },
  });

export const listInquiries = (params: Record<string, unknown>) =>
  adminRequest<Page<Inquiry>>(`/api/admin/inquiries${qs(params)}`);
export const setInquiryStatus = (id: number, status: InquiryStatus) =>
  adminRequest<Inquiry>(`/api/admin/inquiries/${id}`, { method: "PATCH", body: { status } });
export const recordSale = (
  id: number,
  body: { price: string; product_id?: number; payment: { method: PaymentMethod } | null; note: string | null },
) => adminRequest<Inquiry>(`/api/admin/inquiries/${id}/sale`, { method: "POST", body });
export const recordPayment = (orderNumber: string, method: PaymentMethod, reference?: string) =>
  adminRequest<OrderDetail>(`/api/admin/orders/${orderNumber}/payments`, {
    method: "POST",
    body: { method, reference: reference || null },
  });

export const listCustomers = (params: Record<string, unknown>) =>
  adminRequest<Page<Customer>>(`/api/admin/customers${qs(params)}`);
export const getCustomer = (id: number) =>
  adminRequest<CustomerDetail>(`/api/admin/customers/${id}`);

/* Promotions */
export const listPromotions = () => adminRequest<Promotion[]>("/api/admin/promotions");
export const createPromotion = (body: unknown) =>
  adminRequest<Promotion>("/api/admin/promotions", { method: "POST", body });
export const updatePromotion = (id: number, body: unknown) =>
  adminRequest<Promotion>(`/api/admin/promotions/${id}`, { method: "PATCH", body });
export const deactivatePromotion = (id: number) =>
  adminRequest<{ message: string }>(`/api/admin/promotions/${id}`, { method: "DELETE" });

/* Content */
export const listPosts = (params: Record<string, unknown> = {}) =>
  adminRequest<Page<Post>>(`/api/admin/posts${qs(params)}`);
export const createPost = (body: unknown) =>
  adminRequest<Post>("/api/admin/posts", { method: "POST", body });
export const updatePost = (id: number, body: unknown) =>
  adminRequest<Post>(`/api/admin/posts/${id}`, { method: "PATCH", body });
export const archivePost = (id: number) =>
  adminRequest<{ message: string }>(`/api/admin/posts/${id}`, { method: "DELETE" });

export const listHomepageSections = () =>
  adminRequest<HomepageSection[]>("/api/admin/homepage/sections");
export const saveHomepageSection = (body: unknown) =>
  adminRequest<HomepageSection>("/api/admin/homepage/sections", {
    method: "PUT",
    body,
  });

export const listSocialLinks = () =>
  adminRequest<SocialLink[]>("/api/admin/social-links");
export const saveSocialLink = (body: unknown) =>
  adminRequest<SocialLink>("/api/admin/social-links", { method: "PUT", body });
export const deleteSocialLink = (id: number) =>
  adminRequest<{ message: string }>(`/api/admin/social-links/${id}`, {
    method: "DELETE",
  });

export const getAdminSettings = () =>
  adminRequest<SiteSettings>("/api/admin/settings");
export const updateAdminSettings = (body: unknown) =>
  adminRequest<SiteSettings>("/api/admin/settings", { method: "PATCH", body });
