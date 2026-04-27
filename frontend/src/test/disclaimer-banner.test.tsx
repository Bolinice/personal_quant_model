import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import DisclaimerBanner from '@/components/compliance/DisclaimerBanner'

describe('DisclaimerBanner', () => {
  it('renders simple variant by default', () => {
    render(<DisclaimerBanner />)
    expect(screen.getByText(/本平台内容仅供研究与学习使用/)).toBeInTheDocument()
  })

  it('renders full variant', () => {
    render(<DisclaimerBanner variant="full" />)
    expect(screen.getByText(/本平台为量化研究与历史分析工具/)).toBeInTheDocument()
  })

  it('renders page variant with backtest type', () => {
    render(<DisclaimerBanner variant="page" pageType="backtest" />)
    expect(screen.getByText(/本回测结果基于历史数据模拟/)).toBeInTheDocument()
  })

  it('renders page variant with portfolio type', () => {
    render(<DisclaimerBanner variant="page" pageType="portfolio" />)
    expect(screen.getByText(/本模拟组合仅供量化研究参考/)).toBeInTheDocument()
  })

  it('renders page variant with signal type', () => {
    render(<DisclaimerBanner variant="page" pageType="signal" />)
    expect(screen.getByText(/以下信号由量化模型自动生成/)).toBeInTheDocument()
  })

  it('renders page variant with factor type', () => {
    render(<DisclaimerBanner variant="page" pageType="factor" />)
    expect(screen.getByText(/因子IC值和收益率均为历史统计结果/)).toBeInTheDocument()
  })

  it('falls back to simple for unknown page type', () => {
    render(<DisclaimerBanner variant="page" pageType={'unknown' as any} />)
    expect(screen.getByText(/本平台内容仅供研究与学习使用/)).toBeInTheDocument()
  })
})