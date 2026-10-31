import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Suspense, lazy } from "react";
import { BrowserRouter, Link, Route, Routes } from "react-router";
import { AdminLayout, SiteLayout } from "./components/layouts";
import { Loading } from "./components/ui";
import { ApiError } from "./lib/api";
import { CartProvider } from "./lib/cart";
import { RequireAdmin, RequireUser } from "./lib/auth";
import Home from "./pages/Home";

// Owner and admin screens load only when someone opens them, so the home page stays small.
const Login = lazy(() => import("./pages/Login"));
const Register = lazy(() => import("./pages/Register"));
const ForgotPassword = lazy(() => import("./pages/ForgotPassword"));
const Account = lazy(() => import("./pages/Account"));
const Activate = lazy(() => import("./pages/Activate"));
const TagDetail = lazy(() => import("./pages/TagDetail"));
const CardPage = lazy(() => import("./pages/CardPage"));
const ChangePhone = lazy(() => import("./pages/ChangePhone"));
const DeleteAccount = lazy(() => import("./pages/DeleteAccount"));
const Shop = lazy(() => import("./pages/Shop"));
const Cart = lazy(() => import("./pages/Cart"));
const Checkout = lazy(() => import("./pages/Checkout"));
const Orders = lazy(() => import("./pages/Orders"));
const OrderDetail = lazy(() => import("./pages/OrderDetail"));
const PayMock = lazy(() => import("./pages/PayMock"));

const AdminLogin = lazy(() => import("./pages/admin/AdminLogin"));
const Overview = lazy(() => import("./pages/admin/Overview"));
const Batches = lazy(() => import("./pages/admin/Batches"));
const Tags = lazy(() => import("./pages/admin/Tags"));
const AdminTagDetail = lazy(() => import("./pages/admin/AdminTagDetail"));
const Users = lazy(() => import("./pages/admin/Users"));
const Activity = lazy(() => import("./pages/admin/Activity"));
const Deletions = lazy(() => import("./pages/admin/Deletions"));
const AdminOrders = lazy(() => import("./pages/admin/AdminOrders"));
const AdminOrderDetail = lazy(() => import("./pages/admin/AdminOrderDetail"));
const AdminProducts = lazy(() => import("./pages/admin/AdminProducts"));

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      // Retrying a 401, 404 or validation error will never help. Network and server errors get one more go.
      retry: (failures, error) => !(error instanceof ApiError && error.status >= 400 && error.status < 500) && failures < 2,
    },
  },
});

function NotFound() {
  return (
    <div className="py-16 text-center">
      <h1 className="text-2xl font-bold">Page not found</h1>
      <p className="mt-2 text-muted">The page you are looking for does not exist.</p>
      <Link to="/" className="mt-4 inline-block font-medium text-brand">
        Go to the home page
      </Link>
    </div>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <CartProvider>
      <BrowserRouter>
        <Suspense fallback={<Loading />}>
          <Routes>
            <Route element={<SiteLayout />}>
              <Route index element={<Home />} />
              <Route path="login" element={<Login />} />
              <Route path="register" element={<Register />} />
              <Route path="forgot-password" element={<ForgotPassword />} />
              <Route path="shop" element={<Shop />} />
              <Route path="cart" element={<Cart />} />
              <Route path="checkout" element={<RequireUser><Checkout /></RequireUser>} />
              <Route path="orders" element={<RequireUser><Orders /></RequireUser>} />
              <Route path="orders/:number" element={<RequireUser><OrderDetail /></RequireUser>} />
              <Route path="pay/mock/:id" element={<RequireUser><PayMock /></RequireUser>} />
              <Route path="account" element={<RequireUser><Account /></RequireUser>} />
              <Route path="account/tags/:code" element={<RequireUser><TagDetail /></RequireUser>} />
              <Route path="account/card" element={<RequireUser><CardPage /></RequireUser>} />
              <Route path="account/mobile" element={<RequireUser><ChangePhone /></RequireUser>} />
              <Route path="account/delete" element={<RequireUser><DeleteAccount /></RequireUser>} />
              <Route path="activate/:code" element={<RequireUser><Activate /></RequireUser>} />
            </Route>

            <Route path="admin/login" element={<AdminLogin />} />
            <Route path="admin" element={<RequireAdmin><AdminLayout /></RequireAdmin>}>
              <Route index element={<Overview />} />
              <Route path="orders" element={<AdminOrders />} />
              <Route path="orders/:number" element={<AdminOrderDetail />} />
              <Route path="products" element={<AdminProducts />} />
              <Route path="batches" element={<Batches />} />
              <Route path="tags" element={<Tags />} />
              <Route path="tags/:code" element={<AdminTagDetail />} />
              <Route path="users" element={<Users />} />
              <Route path="deletions" element={<Deletions />} />
              <Route path="activity" element={<Activity />} />
            </Route>

            <Route element={<SiteLayout />}>
              <Route path="*" element={<NotFound />} />
            </Route>
          </Routes>
        </Suspense>
      </BrowserRouter>
      </CartProvider>
    </QueryClientProvider>
  );
}
