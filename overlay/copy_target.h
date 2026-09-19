/* GX BP4D stores destination pitch in 32-byte units (16 YUV pixels).
 * Swap also uses GXCopyDisp with zero pitch to clear into a tiny junk buffer.
 * Never let a display overlay write to that non-display destination. */
static int menu_display_copy(unsigned stride,unsigned picture){
 unsigned width=(stride&1023u)*16u;
 return (stride&0xfffffc00u)==0x4d000000u &&
        width>=512u && width<=720u &&
        width==((picture>>8)&127u)*16u;
}
