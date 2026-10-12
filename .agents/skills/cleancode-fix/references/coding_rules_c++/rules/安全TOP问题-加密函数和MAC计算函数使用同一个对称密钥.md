# 安全TOP问题-加密函数和MAC计算函数使用同一个对称密钥

- **规则ID**：e38d23e5-9b2d-445a-b0fd-16b824218a5a
- **更新时间**：2025-03-25 19:23:51

---

**【问题级别】**

一般

**【描述】**

加密函数和MAC计算函数使用同一个对称密钥

**【正确示例】**

```
void Same_Key_good02(CRYPT_CTX *pCtx, SEC_UINT32 ulAlgId, SEC_UCHAR *pucKey, SEC_UINT32 ulKeyLen, SEC_UCHAR *pucIV,
    SEC_UINT32 ulIVLen, VOS_HMAC_CTX *stHmacCtx, VOS_UINT8 *szKey, VOS_HMAC_HASH *stHmacHash)
{
    VOS_HMAC_Init(stHmacCtx, szKey, ulKeyLen, stHmacHash);
    /* Good: 使用不同的密钥 */
    CRYPT_encryptInit(pCtx, ulAlgId, pucKey, ulKeyLen, pucIV, ulIVLen);
}

```
**【错误示例】**

```
【Instruction】&nbsp;&nbsp;1.覆盖的加密函数：CRYPT_encrypt、CRYPT_encryptInit、CRYPT_pubKeyEncrypt、CRYPT_privKeyEncrypt、CRYPT_sm2PkeaEncrypt、EVP_EncryptInit、EVP_EncryptInit_ex
2.覆盖的MAC函数：VOS_HMAC_Init、 HMAC_Init、HMAC_Init_ex、HMAC、CMAC_Init、CRYPT_hmacInit、CRYPT_hmac、CRYPT_cmac、CRYPT_cmacInit、ipsi_hmac_sha224_init、ipsi_hmac_sha256_init、
ipsi_hmac_sha384_init、ipsi_hmac_sha512_init、
 ipsi_hmac_sm3_init
3.同一函数中加密函数和MAC计算函数的密钥参数一致告警【Example】&nbsp;&nbsp;//同一函数中加密函数和MAC计算函数的密钥参数不一致。
 void test_good( CRYPT_CTX* pCtx,SEC_UINT32 ulAlgId,SEC_UCHAR* pucKey, SEC_UINT32 ulKeyLen, SEC_UCHAR* pucIV,SEC_UINT32 ulIVLen,VOS_HMAC_CTX *stHmacCtx,VOS_UINT8 *szKey,VOS_HMAC_HASH *stHmacHash,,VOS_UINT8 *szKey2)
{
 VOS_HMAC_Init(stHmacCtx,szKey,ulKeyLen,stHmacHash);
 CRYPT_encryptInit(pCtx,ulAlgId, szKey2,ulKeyLen,pucIV,ulIVLen);
}//同一函数中加密函数和MAC计算函数的密钥参数一致。
 void test_error( CRYPT_CTX* pCtx,SEC_UINT32 ulAlgId,SEC_UCHAR* pucKey, SEC_UINT32 ulKeyLen, SEC_UCHAR* pucIV,SEC_UINT32 ulIVLen,VOS_HMAC_CTX *stHmacCtx,VOS_UINT8 *szKey,VOS_HMAC_HASH *stHmacHash)
{
 VOS_HMAC_Init(stHmacCtx,szKey,ulKeyLen,stHmacHash);
 CRYPT_encryptInit(pCtx,ulAlgId, szKey,ulKeyLen,pucIV,ulIVLen);
}

```
**【修复建议】**

参照《安全及隐私保护设计检视Checklist_v3.0》对应子检查项D-CAS-19-1：同一笔业务中，若既需要加密运算也需要计算MAC时，加密操作和计算MAC操作不能使用同一个对称密。
