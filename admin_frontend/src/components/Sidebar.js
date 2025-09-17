import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import {
  LayoutDashboard,
  Package,
  Tag,
  Users,
  ShoppingCart,
  Warehouse,
  BarChart3,
  Settings,
  Menu
} from 'lucide-react';

const menuItems = [
  { path: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
  { path: '/products', icon: Package, label: 'Products' },
  { path: '/categories', icon: Tag, label: 'Categories' },
  { path: '/users', icon: Users, label: 'Users' },
  { path: '/sales', icon: ShoppingCart, label: 'Sales' },
  { path: '/inventory', icon: Warehouse, label: 'Inventory' },
  { path: '/reports', icon: BarChart3, label: 'Reports' },
  { path: '/settings', icon: Settings, label: 'Settings' },
];

function Sidebar({ isOpen }) {
  const location = useLocation();

  return (
    <div className={`${isOpen ? 'w-64' : 'w-16'} bg-white shadow-lg transition-all duration-300`}>
      <div className="p-4">
        <h2 className={`text-xl font-bold text-gray-800 ${!isOpen && 'hidden'}`}>
          POS Admin
        </h2>
      </div>
      <nav className="mt-8">
        {menuItems.map((item) => {
          const Icon = item.icon;
          const isActive = location.pathname === item.path;
          return (
            <Link
              key={item.path}
              to={item.path}
              className={`flex items-center px-4 py-3 text-gray-700 hover:bg-gray-100 transition-colors ${
                isActive ? 'bg-blue-50 text-blue-600 border-r-4 border-blue-600' : ''
              }`}
            >
              <Icon className="w-5 h-5 mr-3" />
              {isOpen && <span>{item.label}</span>}
            </Link>
          );
        })}
      </nav>
    </div>
  );
}

export default Sidebar;