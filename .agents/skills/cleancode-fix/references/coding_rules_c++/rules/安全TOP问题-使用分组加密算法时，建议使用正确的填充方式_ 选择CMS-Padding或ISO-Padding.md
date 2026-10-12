# 安全TOP问题-使用分组加密算法时，建议使用正确的填充方式: 选择CMS-Padding或ISO-Padding

- **规则ID**：e3d1abe0-d63a-4064-af3e-62aca5bb2d84
- **更新时间**：2025-03-25 19:23:58

---

**【问题级别】**

一般

**【描述】**

安全设计规范：D-CAS-21-1：使用分组加密算法时，填充方式建议选择CMS-Padding 或ISO-Padding

**【正确示例】**

```
void good() {
  EVP_CIPHER_CTX_set_padding(..,1,..);
  CRYPT_encrypt(3,...);
  CRYPT_encryptInit(..,3,...);
}

```
**【错误示例】**

```
【Instruction】1.定位到EVP_CIPHER_CTX_set_padding函数，获取第二个参数值，如果值为0，告警；
2.定位到CRYPT_encrypt函数，获取第一个参数，如果参数的高8位是2，告警；
3.定位到CRYPT_encryptInit函数，获取第二个参数，如果参数的高8位是2，告警；
【Example】void bad() {
   EVP_CIPHER_CTX_set_padding(..,0,..);//告警
   CRYPT_encrypt(256,...);//告警
   CRYPT_encryptInit(..,256,...);//告警
}

```
**【修复建议】**

参照《安全及隐私保护设计检视Checklist_v3.0》对应子检查项D-CAS-21-1：使用分组加密算法时，填充方式建议选择CMS-Padding 或ISO-Padding
