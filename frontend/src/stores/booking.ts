import { defineStore } from 'pinia'

/**
 * 订舱受理的定位状态：
 * - 航线、托运人选好后翻页必须保持，进入单票详情再返回也要还原；
 * - 滚动位置一并记住，返回列表时停在刚才的位置。
 */
export const useBookingStore = defineStore('booking', {
  state: () => ({
    route: '',
    shipper: '',
    page: 1,
    size: 10,
    scrollY: 0,
  }),
  actions: {
    setRoute(route: string) {
      this.route = route
      // 换定位条件后结果集变了，回到第一页
      this.page = 1
    },
    setShipper(shipper: string) {
      this.shipper = shipper
      this.page = 1
    },
    setPage(page: number) {
      this.page = page
    },
    setSize(size: number) {
      this.size = size
      this.page = 1
    },
    saveScroll(y: number) {
      this.scrollY = y
    },
    resetScroll() {
      this.scrollY = 0
    },
    reset() {
      this.route = ''
      this.shipper = ''
      this.page = 1
      this.size = 10
      this.scrollY = 0
    },
  },
})
