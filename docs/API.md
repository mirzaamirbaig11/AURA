# AURA Clothing Store Documentation

## API Endpoints

### Public Endpoints

- `GET /` - Homepage
- `GET /shop` - Product listing with filters
- `GET /product/<id>` - Product details
- `GET /auth/login` - Login page
- `GET /auth/register` - Registration page
- `POST /auth/register` - Register new customer
- `POST /newsletter/subscribe` - Subscribe to newsletter

### Authenticated Customer Endpoints

- `GET /cart` - View shopping cart
- `POST /cart/add` - Add item to cart
- `POST /cart/update` - Update cart item quantity
- `POST /cart/remove/<id>` - Remove item from cart
- `GET /wishlist` - View wishlist
- `POST /wishlist/toggle` - Toggle product in wishlist
- `GET /checkout` - Checkout page
- `POST /checkout` - Place order
- `GET /orders` - Order history
- `GET /order/<id>` - Order details
- `GET /account` - Account settings
- `POST /account/update` - Update profile

### API Routes (/api)

- `GET /api/products` - JSON product list
- `GET /api/products/<id>` - Single product JSON
- `GET /api/categories` - JSON categories list
- `GET /api/cart` - Cart JSON
- `POST /api/cart/add` - Add to cart via API
- `POST /api/cart/update` - Update cart via API
- `POST /api/wishlist/toggle` - Toggle wishlist via API
- `POST /api/newsletter/subscribe` - Subscribe via API

### Admin Endpoints (/admin)

- `GET /admin/` or `/admin/dashboard` - Dashboard
- `GET /admin/products` - Product listing
- `GET /admin/products/add` - Add product form
- `GET /admin/products/edit/<id>` - Edit product form
- `POST /admin/products/delete/<id>` - Delete product
- `GET /admin/categories` - Category listing
- `GET /admin/categories/add` - Add category form
- `GET /admin/categories/edit/<id>` - Edit category form
- `POST /admin/categories/delete/<id>` - Delete category
- `GET /admin/orders` - Order listing
- `GET /admin/orders/<id>` - Order details
- `POST /admin/orders/<id>/status` - Update order status
- `GET /admin/customers` - Customer listing
- `GET /admin/customers/<id>` - Customer details
- `POST /admin/customers/<id>/toggle` - Toggle customer status
- `GET /admin/inventory` - Inventory listing
- `POST /admin/inventory/update/<id>` - Update inventory
- `GET /admin/settings` - Store settings

## Database Schema

### Tables

| Table | Description |
|-------|-------------|
| admins | Admin users |
| customers | Registered customers |
| customer_addresses | Customer delivery addresses |
| categories | Product categories |
| products | Products |
| product_images | Product images |
| product_sizes | Available sizes |
| inventory | Stock per product/sizes |
| carts | Shopping carts |
| cart_items | Cart items |
| wishlists | Wishlists |
| wishlist_items | Wishlist items |
| orders | Orders |
| order_items | Order items |
| coupons | Discount coupons |
| reviews | Product reviews |
| newsletter_subscribers | Newsletter emails |
| audit_logs | Admin action logs |

## Default Categories (8)

1. Jersey
2. Jeans
3. T-Shirts
4. Shirts
5. Hoodies
6. Cargoes
7. Trousers
8. Jackets

## Brand Information

- **Business Name**: AURA
- **Type**: Premium luxury streetwear
- **Brand Colors**: Red (#e60000), Black, White
- **Tagline**: Premium luxury streetwear. Modern editorial fashion.

### Contact Links

- WhatsApp: https://wa.me/918527756728
- Instagram: https://instagram.com/aura_clothing
- Google Maps: https://maps.app.goo.gl/pRC9ZQcwyDGbPo5Q9

## Project Status

- ✅ Backend API complete
- ✅ Admin Dashboard complete
- ✅ Customer Frontend complete
- ✅ Database models complete
- ✅ Authentication system complete
- ✅ Shopping cart complete
- ✅ Checkout flow complete
- ✅ Order management complete
- ✅ Inventory management complete
- ✅ Automated tests (7 passing)
- ⏳ Payment gateway (disabled - for future integration)