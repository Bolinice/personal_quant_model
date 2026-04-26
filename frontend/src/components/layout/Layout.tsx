import { useState, useEffect } from 'react';
import { Layout as AntLayout, Menu, Button, Dropdown, Avatar, message } from 'antd';
import {
  DashboardOutlined,
  ExperimentOutlined,
  FundOutlined,
  BarChartOutlined,
  SettingOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  UserOutlined,
  LogoutOutlined,
  CrownOutlined,
} from '@ant-design/icons';
import { useNavigate, useLocation, Outlet } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import ComplianceModal from '@/components/compliance/ComplianceModal';

const { Header, Sider, Content, Footer } = AntLayout;

const menuItems = [
  { key: '/app/dashboard', icon: <DashboardOutlined />, label: '工作台' },
  { key: '/app/factors', icon: <ExperimentOutlined />, label: '因子研究' },
  { key: '/app/backtests', icon: <FundOutlined />, label: '策略回测' },
  { key: '/app/portfolios', icon: <BarChartOutlined />, label: '组合管理' },
  { key: '/app/subscribe', icon: <CrownOutlined />, label: '订阅方案' },
  { key: '/app/settings', icon: <SettingOutlined />, label: '设置' },
];

export default function Layout() {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuth();
  const [collapsed, setCollapsed] = useState(false);
  const [complianceVisible, setComplianceVisible] = useState(false);

  useEffect(() => {
    if (!localStorage.getItem('compliance_workbench_shown')) {
      setComplianceVisible(true);
    }
  }, []);

  const handleMenuClick = ({ key }: { key: string }) => {
    navigate(key);
  };

  const handleLogout = () => {
    logout();
    navigate('/auth/login');
  };

  const userMenuItems = [
    { key: 'profile', icon: <UserOutlined />, label: '个人设置' },
    { key: 'logout', icon: <LogoutOutlined />, label: '退出登录' },
  ];

  const handleUserMenu = ({ key }: { key: string }) => {
    if (key === 'logout') handleLogout();
    else if (key === 'profile') navigate('/app/settings');
  };

  return (
    <AntLayout style={{ minHeight: '100vh' }}>
      <Sider
        trigger={null}
        collapsible
        collapsed={collapsed}
        theme="dark"
        style={{
          overflow: 'auto',
          height: '100vh',
          position: 'fixed',
          left: 0,
          top: 0,
          bottom: 0,
          zIndex: 10,
        }}
      >
        <div style={{ height: 32, margin: 16, color: '#fff', textAlign: 'center', fontSize: collapsed ? 14 : 18, fontWeight: 700 }}>
          {collapsed ? 'Q' : 'QuantPro'}
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[location.pathname]}
          items={menuItems}
          onClick={handleMenuClick}
        />
      </Sider>
      <AntLayout style={{ marginLeft: collapsed ? 80 : 200, transition: 'all 0.2s' }}>
        <Header style={{ padding: '0 24px', background: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'space-between', boxShadow: '0 1px 4px rgba(0,0,0,0.1)' }}>
          <Button
            type="text"
            icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
            onClick={() => setCollapsed(!collapsed)}
          />
          <Dropdown menu={{ items: userMenuItems, onClick: handleUserMenu }} placement="bottomRight">
            <div style={{ cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8 }}>
              <Avatar icon={<UserOutlined />} />
              <span>{user?.username || '用户'}</span>
            </div>
          </Dropdown>
        </Header>
        <Content style={{ margin: 24, padding: 24, background: '#fff', borderRadius: 8, minHeight: 280 }}>
          <Outlet />
        </Content>
        <Footer style={{ textAlign: 'center', color: '#999' }}>
          A股多因子增强策略平台 ©{new Date().getFullYear()} · 仅供研究使用，不构成投资建议
        </Footer>
      </AntLayout>
      <ComplianceModal storageKey="compliance_workbench_shown" />
    </AntLayout>
  );
}
