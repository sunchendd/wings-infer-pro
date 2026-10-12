# G.OTH.01 安全场景下必须使用密码学意义上的安全随机数

- **规则ID**：6438d84a-cb5e-4da8-917e-30d45f743907
- **更新时间**：2025-06-05 04:35:02

---

**【问题级别】**

一般

**【描述】**

不安全的随机数可能被部分或全部预测到，导致系统存在安全隐患，安全场景下使用的随机数必须是密码学意义上的安全随机数。

在javascript中经常使用Math.Random()函数来产生随机数，但该函数依赖于弱伪随机数生成器，其不具有真正的随机性，而且加密性也不够强，因此在对安全性要求较高的场景中，不应使用Math.Random()函数来产生随机数，应使用加密性较强的crypto库来生成随机数。

**【正确示例】**

```
crypto = window.crypto || window.msCrypto;
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

安全场景下必须使用密码学意义上的安全随机数
