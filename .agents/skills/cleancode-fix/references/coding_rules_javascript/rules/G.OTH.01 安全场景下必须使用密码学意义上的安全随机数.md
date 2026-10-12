# G.OTH.01 安全场景下必须使用密码学意义上的安全随机数

- **规则ID**：eda9e1e3-5a7e-459e-bbab-5033d9d6bd15
- **更新时间**：2025-06-05 04:25:02

---

**【问题级别】**

严重

**【描述】**

不安全的随机数可能被部分或全部预测到，导致系统存在安全隐患，安全场景下使用的随机数必须是密码学意义上的安全随机数。

**【正确示例】**

```
// === 客户端 ===
const crypto = window.crypto || window.msCrypto;
let array = new Uint32Array(1);
crypto.getRandomValues(array); 
// === 服务器端 ===
const crypto = require('crypto');
const buf = crypto.randomBytes(1); 

```
**【错误示例】**

```
const val = Math.random();

```
**【修复建议】**

使用密码学意义上的安全随机数
